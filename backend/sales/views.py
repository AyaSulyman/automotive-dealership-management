from django.http import HttpResponse
from django.utils import timezone
from django.utils.crypto import get_random_string
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAdmin, IsAdminAgentOrAccountant, IsAdminOrAgent
from common.pdf import render_simple_document

from .integrations import mark_vehicle_sold
from .models import Discount, SalesInvoice, TaxRule, TradeIn
from .serializers import (
    ApplyCreditSerializer, DiscountCreateSerializer, DiscountSerializer,
    SalesInvoiceCreateSerializer, SalesInvoiceSerializer, SalesInvoiceUpdateSerializer,
    TaxRuleSerializer, TradeInSerializer,
)


class TradeInListCreateView(generics.ListCreateAPIView):
    """
    POST /trade-ins        Capture appraisal.
    """
    queryset = TradeIn.objects.all()
    serializer_class = TradeInSerializer
    permission_classes = [IsAdminOrAgent]
    filterset_fields = ["customer_id"]

    def perform_create(self, serializer):
        serializer.save(appraised_by=self.request.user)


class TradeInDetailView(generics.RetrieveUpdateAPIView):
    """
    GET   /trade-ins/{id}     Trade-in detail.
    PATCH /trade-ins/{id}     Edit appraisal before it's credited.
    """
    queryset = TradeIn.objects.all()
    serializer_class = TradeInSerializer
    permission_classes = [IsAdminOrAgent]

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_credited:
            return Response(
                {"error": {"code": "conflict", "message": "This trade-in has already been credited to an invoice and can no longer be edited.", "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )
        return super().update(request, *args, **kwargs)


class TradeInApplyCreditView(APIView):
    """
    POST /trade-ins/{id}/apply-credit
    Body: {"invoice_id": <int>}
    Sets credited_invoice_id and returns a generated reference code
    (e.g. "TRD-993-A2") matching the "Credited Invoice ID (Generated)"
    field shown on the Sales & Trade-Ins screen.
    """
    permission_classes = [IsAdminOrAgent]

    def post(self, request, pk):
        trade_in = generics.get_object_or_404(TradeIn, pk=pk)
        if trade_in.is_credited:
            return Response(
                {"error": {"code": "conflict", "message": "Trade-in is already credited to an invoice.", "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = ApplyCreditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = generics.get_object_or_404(SalesInvoice, pk=serializer.validated_data["invoice_id"])
        if invoice.status != "DRAFT":
            return Response(
                {"error": {"code": "conflict", "message": "Trade-ins can only be credited to a DRAFT deal.", "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )

        reference = f"TRD-{trade_in.pk:03d}-{get_random_string(2, allowed_chars='ABCDEFGHJKLMNPQRSTUVWXYZ23456789')}"
        trade_in.credited_invoice_id = invoice.pk
        trade_in.credited_reference = reference
        trade_in.save(update_fields=["credited_invoice", "credited_reference", "updated_at"])

        invoice.trade_in_credit = invoice.trade_in_credit + trade_in.appraised_value
        invoice.recompute_totals(tax_rate=_active_tax_rate())
        invoice.save()

        return Response(TradeInSerializer(trade_in).data, status=status.HTTP_200_OK)


class TaxRuleListCreateView(generics.ListCreateAPIView):
    """
    GET  /tax-rules     List tax rules (jurisdiction, is_active filters).
    POST /tax-rules     Create a rate.
    """
    queryset = TaxRule.objects.all()
    serializer_class = TaxRuleSerializer
    permission_classes = [IsAdmin]
    filterset_fields = ["jurisdiction", "is_active"]


class TaxRuleDetailView(generics.RetrieveUpdateAPIView):
    """
    PATCH /tax-rules/{id}   Edit/deactivate a rule.
    """
    queryset = TaxRule.objects.all()
    serializer_class = TaxRuleSerializer
    permission_classes = [IsAdmin]


def _active_tax_rate():
    rule = TaxRule.objects.filter(is_active=True).order_by("id").first()
    return rule.rate if rule else None


class SalesInvoiceListCreateView(generics.ListCreateAPIView):
    """
    GET  /sales-invoices    List/search invoices (customer_id, vehicle_id,
                            status, branch_id filters).
    POST /sales-invoices    Create Deal Worksheet (status DRAFT).
    """
    queryset = SalesInvoice.objects.all()
    permission_classes = [IsAdminOrAgent]
    filterset_fields = ["customer_id", "vehicle_id", "status", "branch_id"]

    def get_serializer_class(self):
        return SalesInvoiceCreateSerializer if self.request.method == "POST" else SalesInvoiceSerializer

    def get_permissions(self):
        # Read access (list) is also open to accountants for reconciliation;
        # only admin/agent can create deals.
        if self.request.method == "GET":
            return [IsAdminAgentOrAccountant()]
        return [IsAdminOrAgent()]

    def perform_create(self, serializer):
        serializer.save()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save()
        invoice.recompute_totals(tax_rate=_active_tax_rate())
        invoice.save()
        return Response(SalesInvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)


class SalesInvoiceDetailView(generics.RetrieveUpdateAPIView):
    """
    GET   /sales-invoices/{id}   Full detail — Deal Summary + printable Invoice.
    PATCH /sales-invoices/{id}   Update a DRAFT deal only.
    """
    queryset = SalesInvoice.objects.all()

    def get_permissions(self):
        # Read access is also open to accountants for reconciliation;
        # only admin/agent can edit a DRAFT deal.
        if self.request.method == "GET":
            return [IsAdminAgentOrAccountant()]
        return [IsAdminOrAgent()]

    def get_serializer_class(self):
        return SalesInvoiceUpdateSerializer if self.request.method == "PATCH" else SalesInvoiceSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != "DRAFT":
            return Response(
                {"error": {"code": "conflict", "message": "Only DRAFT deals can be edited.", "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save()
        invoice.recompute_totals(tax_rate=_active_tax_rate())
        invoice.save()
        return Response(SalesInvoiceSerializer(invoice).data)


class SalesInvoiceSaveDraftView(APIView):
    """POST /sales-invoices/{id}/save-draft — explicit "Save Draft" action."""
    permission_classes = [IsAdminOrAgent]

    def post(self, request, pk):
        invoice = generics.get_object_or_404(SalesInvoice, pk=pk)
        if invoice.status != "DRAFT":
            return Response(
                {"error": {"code": "conflict", "message": "Deal is no longer a draft.", "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )
        invoice.recompute_totals(tax_rate=_active_tax_rate())
        invoice.save()
        return Response(SalesInvoiceSerializer(invoice).data)


class SalesInvoiceFinalizeView(APIView):
    """
    POST /sales-invoices/{id}/finalize
    Validates trade-in/discount, generates invoice_number, sets status=OPEN,
    marks the vehicle SOLD (via the integrations stub).
    """
    permission_classes = [IsAdminOrAgent]

    def post(self, request, pk):
        invoice = generics.get_object_or_404(SalesInvoice, pk=pk)

        if invoice.status != "DRAFT":
            return Response(
                {"error": {"code": "conflict", "message": "Only a DRAFT deal can be finalized.", "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )
        if invoice.total_amount is None or invoice.total_amount <= 0:
            return Response(
                {"error": {"code": "bad_request", "message": "Deal total must be greater than zero before finalizing.", "fields": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        year = timezone.now().year
        invoice.invoice_number = f"INV-{year}-{get_random_string(6, allowed_chars='0123456789')}"
        invoice.sale_date = invoice.sale_date or timezone.now().date()
        invoice.status = "OPEN"
        invoice.recompute_totals(tax_rate=_active_tax_rate())
        invoice.save()

        mark_vehicle_sold(invoice.vehicle_id)

        return Response(SalesInvoiceSerializer(invoice).data)


class SalesInvoiceDiscountsView(APIView):
    """POST /sales-invoices/{id}/discounts — add a line-item discount."""
    permission_classes = [IsAdminOrAgent]

    def post(self, request, pk):
        invoice = generics.get_object_or_404(SalesInvoice, pk=pk)
        if invoice.status != "DRAFT":
            return Response(
                {"error": {"code": "conflict", "message": "Discounts can only be added to a DRAFT deal.", "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = DiscountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        amount = data["amount"]
        if data["discount_type"] == "PERCENTAGE":
            amount = (invoice.selling_price * amount / 100).quantize(invoice.selling_price)

        discount = Discount.objects.create(
            invoice=invoice, discount_type=data["discount_type"],
            amount=amount, reason=data.get("reason", ""),
        )

        invoice.discount_amount = invoice.discount_amount + amount
        invoice.recompute_totals(tax_rate=_active_tax_rate())
        invoice.save()

        return Response(
            {"discount": DiscountSerializer(discount).data, "invoice": SalesInvoiceSerializer(invoice).data},
            status=status.HTTP_201_CREATED,
        )


class SalesInvoicePdfView(APIView):
    """GET /sales-invoices/{id}/pdf — printable invoice."""
    permission_classes = [IsAdminOrAgent]

    def get(self, request, pk):
        invoice = generics.get_object_or_404(SalesInvoice, pk=pk)

        meta = [
            ("Invoice #", invoice.invoice_number or "DRAFT"),
            ("Status", invoice.status),
            ("Sale Date", str(invoice.sale_date or "-")),
            ("Customer ID", str(invoice.customer_id)),
            ("Vehicle ID", str(invoice.vehicle_id)),
            ("Salesperson", invoice.salesperson.get_username()),
        ]
        headers = ["Line Item", "Amount"]
        rows = [
            ["Selling Price", f"{invoice.selling_price:.2f}"],
            ["Discount", f"-{invoice.discount_amount:.2f}"],
            ["Subtotal", f"{invoice.subtotal:.2f}"],
            ["Tax", f"{invoice.tax_amount:.2f}"],
            ["Trade-In Credit", f"-{invoice.trade_in_credit:.2f}"],
        ]
        totals = [
            ("Total", f"{invoice.total_amount:.2f}"),
            ("Balance Due", f"{invoice.balance_due:.2f}"),
        ]

        pdf_bytes = render_simple_document(
            title="INVOICE",
            subtitle=f"Invoice #{invoice.invoice_number or ('DRAFT-' + str(invoice.pk))}",
            meta_pairs=meta,
            table_headers=headers,
            table_rows=rows,
            totals=totals,
            footer_note="Thank you for your business.",
        )
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="invoice-{invoice.pk}.pdf"'
        return response


class SalesInvoiceCancelView(APIView):
    """POST /sales-invoices/{id}/cancel — cancel a DRAFT deal only.
    Full reversal of a finalized invoice (SAL-04) is Future."""
    permission_classes = [IsAdminOrAgent]

    def post(self, request, pk):
        invoice = generics.get_object_or_404(SalesInvoice, pk=pk)
        if invoice.status != "DRAFT":
            return Response(
                {"error": {"code": "conflict", "message": "Only a DRAFT deal can be cancelled here. Reversing a finalized invoice is not yet supported.", "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )
        invoice.status = "CANCELLED"
        invoice.save(update_fields=["status", "updated_at"])
        return Response(SalesInvoiceSerializer(invoice).data)
