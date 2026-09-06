from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.crypto import get_random_string
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAdmin, IsAdminOrAccountant
from common.pdf import render_simple_document

from .models import Discount, SalesInvoice, TaxRule, TradeIn
from reports.audit import log_action
from .serializers import (
    ApplyCreditSerializer, DiscountCreateSerializer, DiscountSerializer,
    SalesInvoiceCreateSerializer, SalesInvoiceSerializer, SalesInvoiceUpdateSerializer,
    TaxRuleSerializer, TradeInSerializer,
)
from .workflow import finalize_invoice, tax_rate, validate_vehicle


@extend_schema_view(
    get=extend_schema(tags=["Trade-Ins"], summary="List trade-ins"),
    post=extend_schema(tags=["Trade-Ins"], summary="Capture a trade-in appraisal"),
)
class TradeInListCreateView(generics.ListCreateAPIView):
    """
    POST /trade-ins        Capture appraisal.
    """
    queryset = TradeIn.objects.all()
    serializer_class = TradeInSerializer
    permission_classes = [IsAdminOrAccountant]
    filterset_fields = ["customer_id"]

    def perform_create(self, serializer):
        serializer.save(appraised_by=self.request.user)


@extend_schema_view(
    get=extend_schema(tags=["Trade-Ins"], summary="Trade-in detail"),
    patch=extend_schema(tags=["Trade-Ins"], summary="Edit a trade-in (blocked once credited)"),
)
class TradeInDetailView(generics.RetrieveUpdateAPIView):
    """
    GET   /trade-ins/{id}     Trade-in detail.
    PATCH /trade-ins/{id}     Edit appraisal before it's credited.
    """
    queryset = TradeIn.objects.all()
    serializer_class = TradeInSerializer
    permission_classes = [IsAdminOrAccountant]

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
    permission_classes = [IsAdminOrAccountant]

    @extend_schema(tags=["Trade-Ins"], summary="Credit a trade-in to a DRAFT invoice",
                   request=ApplyCreditSerializer, responses=TradeInSerializer)
    @transaction.atomic
    def post(self, request, pk):
        trade_in = generics.get_object_or_404(TradeIn.objects.select_for_update(), pk=pk)
        if trade_in.is_credited:
            return Response(
                {"error": {"code": "conflict", "message": "Trade-in is already credited to an invoice.", "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = ApplyCreditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice = generics.get_object_or_404(SalesInvoice.objects.select_for_update(), pk=serializer.validated_data["invoice_id"])
        if invoice.status != "DRAFT":
            return Response(
                {"error": {"code": "conflict", "message": "Trade-ins can only be credited to a DRAFT deal.", "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )
        if trade_in.customer_id != invoice.customer_id:
            return Response(
                {"error": {"code": "bad_request", "message": "The trade-in and invoice must belong to the same customer.", "fields": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if invoice.total_amount - trade_in.appraised_value <= 0:
            return Response(
                {"error": {"code": "bad_request", "message": "The trade-in credit must leave a positive invoice total.", "fields": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reference = f"TRD-{trade_in.pk:03d}-{get_random_string(2, allowed_chars='ABCDEFGHJKLMNPQRSTUVWXYZ23456789')}"
        trade_in.credited_invoice_id = invoice.pk
        trade_in.credited_reference = reference
        trade_in.save(update_fields=["credited_invoice", "credited_reference", "updated_at"])

        invoice.trade_in_credit = invoice.trade_in_credit + trade_in.appraised_value
        invoice.recompute_totals(tax_rate=_active_tax_rate())
        invoice.save()

        log_action(request.user, "UPDATE", "TradeIn", trade_in.pk, {"credited_invoice_id": invoice.pk, "reference": reference})

        return Response(TradeInSerializer(trade_in).data, status=status.HTTP_200_OK)


@extend_schema_view(
    get=extend_schema(tags=["Tax Rules"], summary="List tax rules"),
    post=extend_schema(tags=["Tax Rules"], summary="Create a tax rate"),
)
class TaxRuleListCreateView(generics.ListCreateAPIView):
    """
    GET  /tax-rules     List tax rules (jurisdiction, is_active filters).
    POST /tax-rules     Create a rate.
    """
    queryset = TaxRule.objects.all()
    serializer_class = TaxRuleSerializer
    permission_classes = [IsAdmin]
    filterset_fields = ["jurisdiction", "is_active"]


@extend_schema_view(
    get=extend_schema(tags=["Tax Rules"], summary="Tax rule detail"),
    patch=extend_schema(tags=["Tax Rules"], summary="Edit / deactivate a tax rule"),
)
class TaxRuleDetailView(generics.RetrieveUpdateAPIView):
    """
    PATCH /tax-rules/{id}   Edit/deactivate a rule.
    """
    queryset = TaxRule.objects.all()
    serializer_class = TaxRuleSerializer
    permission_classes = [IsAdmin]


def _active_tax_rate():
    return tax_rate()


@extend_schema_view(
    get=extend_schema(tags=["Sales Invoices"], summary="List / search sales invoices"),
    post=extend_schema(tags=["Sales Invoices"], summary="Create Deal Worksheet (status DRAFT)"),
)
class SalesInvoiceListCreateView(generics.ListCreateAPIView):
    """
    GET  /sales-invoices    List/search invoices (customer_id, vehicle_id,
                            status, branch_id filters).
    POST /sales-invoices    Create Deal Worksheet (status DRAFT).
    """
    queryset = SalesInvoice.objects.all()
    permission_classes = [IsAdminOrAccountant]
    filterset_fields = ["customer_id", "vehicle_id", "status", "branch_id"]

    def get_queryset(self):
        qs = SalesInvoice.objects.select_related("salesperson").prefetch_related("discounts", "trade_ins")
        search = self.request.query_params.get("search", "").strip()
        if search:
            query = Q(invoice_number__icontains=search)
            if search.isdigit():
                query |= Q(pk=int(search))
            qs = qs.filter(query)
        return qs.order_by("-created_at")

    def get_serializer_class(self):
        return SalesInvoiceCreateSerializer if self.request.method == "POST" else SalesInvoiceSerializer

    def get_permissions(self):
        # Read access (list) is also open to accountants for reconciliation;
        # only admin/finance can create deals.
        if self.request.method == "GET":
            return [IsAdminOrAccountant()]
        return [IsAdminOrAccountant()]

    def perform_create(self, serializer):
        serializer.save()

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vehicle_id = serializer.validated_data["vehicle_id"]
        from inventory.models import Vehicle
        vehicle = generics.get_object_or_404(Vehicle.objects.select_for_update(), pk=vehicle_id)
        validate_vehicle(vehicle)
        invoice = serializer.save(salesperson=request.user)
        invoice.recompute_totals(tax_rate=_active_tax_rate())
        if invoice.total_amount <= 0:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"dealer_markup_discount": "Discount must leave a positive total."})
        invoice.save()
        vehicle.status = "RESERVED"
        vehicle.save(update_fields=["status", "updated_at"])
        return Response(SalesInvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(tags=["Sales Invoices"], summary="Sales invoice detail (Deal Summary / printable Invoice source)"),
    patch=extend_schema(tags=["Sales Invoices"], summary="Edit a DRAFT deal"),
)
class SalesInvoiceDetailView(generics.RetrieveUpdateAPIView):
    """
    GET   /sales-invoices/{id}   Full detail — Deal Summary + printable Invoice.
    PATCH /sales-invoices/{id}   Update a DRAFT deal only.
    """
    queryset = SalesInvoice.objects.all()

    def get_permissions(self):
        # Read access is also open to accountants for reconciliation;
        # only admin/finance can edit a DRAFT deal.
        if self.request.method == "GET":
            return [IsAdminOrAccountant()]
        return [IsAdminOrAccountant()]

    def get_serializer_class(self):
        return SalesInvoiceUpdateSerializer if self.request.method == "PATCH" else SalesInvoiceSerializer

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        instance = generics.get_object_or_404(SalesInvoice.objects.select_for_update(), pk=kwargs["pk"])
        if instance.status != "DRAFT":
            return Response(
                {"error": {"code": "conflict", "message": "Only DRAFT deals can be edited.", "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        old_vehicle_id = instance.vehicle_id
        new_vehicle_id = serializer.validated_data.get("vehicle_id", old_vehicle_id)
        from inventory.models import Vehicle
        new_vehicle = generics.get_object_or_404(
            Vehicle.objects.select_for_update(), pk=new_vehicle_id,
        )
        validate_vehicle(new_vehicle, instance)
        invoice = serializer.save()
        invoice.recompute_totals(tax_rate=_active_tax_rate())
        if invoice.total_amount <= 0:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"discount_amount": "Discount must leave a positive total."})
        invoice.save()
        if old_vehicle_id != invoice.vehicle_id:
            old_vehicle = Vehicle.objects.select_for_update().filter(pk=old_vehicle_id, status="RESERVED").first()
            if old_vehicle:
                old_vehicle.status = "AVAILABLE"
                old_vehicle.save(update_fields=["status", "updated_at"])
            new_vehicle.status = "RESERVED"
            new_vehicle.save(update_fields=["status", "updated_at"])
        return Response(SalesInvoiceSerializer(invoice).data)


class SalesInvoiceSaveDraftView(APIView):
    """POST /sales-invoices/{id}/save-draft — explicit "Save Draft" action."""
    permission_classes = [IsAdminOrAccountant]

    @extend_schema(tags=["Sales Invoices"], summary="Save Draft", request=None, responses=SalesInvoiceSerializer)
    @transaction.atomic
    def post(self, request, pk):
        invoice = generics.get_object_or_404(SalesInvoice.objects.select_for_update(), pk=pk)
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
    marks the inventory vehicle SOLD in the same transaction.
    """
    permission_classes = [IsAdminOrAccountant]

    @extend_schema(tags=["Sales Invoices"], summary="Finalize Deal",
                   description="Generates invoice_number, sets status=OPEN, marks the vehicle SOLD.",
                   request=None, responses=SalesInvoiceSerializer)
    @transaction.atomic
    def post(self, request, pk):
        invoice = generics.get_object_or_404(SalesInvoice.objects.select_for_update(), pk=pk)
        finalize_invoice(invoice, request.user)
        return Response(SalesInvoiceSerializer(invoice).data)


class SalesInvoiceDiscountsView(APIView):
    """POST /sales-invoices/{id}/discounts — add a line-item discount."""
    permission_classes = [IsAdminOrAccountant]

    @extend_schema(tags=["Sales Invoices"], summary="Add a line-item discount",
                   request=DiscountCreateSerializer, responses={201: OpenApiTypes.OBJECT})
    @transaction.atomic
    def post(self, request, pk):
        invoice = generics.get_object_or_404(SalesInvoice.objects.select_for_update(), pk=pk)
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
            if data["amount"] > 100:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"amount": "Percentage discounts cannot exceed 100%."})
            amount = (invoice.selling_price * amount / 100).quantize(invoice.selling_price)

        invoice.discount_amount = invoice.discount_amount + amount
        invoice.recompute_totals(tax_rate=_active_tax_rate())
        if invoice.total_amount <= 0:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"amount": "Discount must leave a positive invoice total."})
        discount = Discount.objects.create(
            invoice=invoice, discount_type=data["discount_type"],
            amount=amount, reason=data.get("reason", ""),
        )
        invoice.save()

        return Response(
            {"discount": DiscountSerializer(discount).data, "invoice": SalesInvoiceSerializer(invoice).data},
            status=status.HTTP_201_CREATED,
        )


class SalesInvoicePdfView(APIView):
    """GET /sales-invoices/{id}/pdf — printable invoice."""
    permission_classes = [IsAdminOrAccountant]

    @extend_schema(tags=["Sales Invoices"], summary="Printable invoice (PDF)",
                   responses={200: OpenApiTypes.BINARY})
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
    permission_classes = [IsAdminOrAccountant]

    @extend_schema(tags=["Sales Invoices"], summary="Cancel a DRAFT deal", request=None, responses=SalesInvoiceSerializer)
    @transaction.atomic
    def post(self, request, pk):
        invoice = generics.get_object_or_404(SalesInvoice.objects.select_for_update(), pk=pk)
        if invoice.status != "DRAFT":
            return Response(
                {"error": {"code": "conflict", "message": "Only a DRAFT deal can be cancelled here. Reversing a finalized invoice is not yet supported.", "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )
        invoice.status = "CANCELLED"
        invoice.save(update_fields=["status", "updated_at"])
        from inventory.models import Vehicle
        vehicle = Vehicle.objects.select_for_update().filter(pk=invoice.vehicle_id, status="RESERVED").first()
        if vehicle:
            vehicle.status = "AVAILABLE"
            vehicle.save(update_fields=["status", "updated_at"])
        log_action(request.user, "UPDATE", "SalesInvoice", invoice.pk, {"status": "CANCELLED"})
        return Response(SalesInvoiceSerializer(invoice).data)
