import csv

from django.http import HttpResponse
from django.utils import timezone
from django.utils.crypto import get_random_string
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAdminAgentOrAccountant, IsAdminOrAccountant
from common.pdf import render_simple_document

from .models import Payment, PaymentSchedule, FinancingAccount
from .schedule_sync import apply_payment_to_schedule
from .serializers import (
    FinancingAccountSerializer, FinancingAccountStatusUpdateSerializer,
    GenerateScheduleSerializer, PaymentCreateSerializer, PaymentScheduleSerializer, PaymentSerializer,
)


def _generate_receipt_number():
    year = timezone.now().year
    return f"RCT-{year}-{get_random_string(6, allowed_chars='0123456789')}"


class PaymentListCreateView(generics.ListCreateAPIView):
    """
    GET  /payments   List/filter -- Payments Ledger table.
    POST /payments   "Record Payment."
    """
    queryset = Payment.objects.select_related("invoice").all()
    permission_classes = [IsAdminOrAccountant]
    filterset_fields = ["invoice", "method"]

    def get_serializer_class(self):
        return PaymentCreateSerializer if self.request.method == "POST" else PaymentSerializer

    def get_permissions(self):
        # Recording a payment is also open to agents (e.g. taking a down
        # payment at the point of sale); everything else is admin/accountant.
        if self.request.method == "POST":
            return [IsAdminAgentOrAccountant()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        payment = Payment.objects.create(
            receipt_number=_generate_receipt_number(),
            recorded_by=request.user,
            **data,
        )

        invoice = payment.invoice
        invoice.balance_due = invoice.balance_due - payment.amount
        if invoice.balance_due <= 0:
            invoice.balance_due = 0
            invoice.status = "PAID"
        invoice.save(update_fields=["balance_due", "status", "updated_at"])

        apply_payment_to_schedule(invoice, payment.amount, payment.paid_at)

        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class PaymentDetailView(generics.RetrieveAPIView):
    """GET /payments/{id} -- payment detail."""
    queryset = Payment.objects.select_related("invoice").all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAdminOrAccountant]


class PaymentReceiptView(APIView):
    """GET /payments/{id}/receipt -- printable/PDF receipt."""
    permission_classes = [IsAdminAgentOrAccountant]

    def get(self, request, pk):
        payment = generics.get_object_or_404(Payment, pk=pk)
        invoice = payment.invoice

        meta = [
            ("Receipt #", payment.receipt_number),
            ("Invoice #", invoice.invoice_number or f"DRAFT-{invoice.pk}"),
            ("Paid At", str(payment.paid_at)),
            ("Method", payment.get_method_display()),
            ("Reference", payment.reference_number or "-"),
            ("Recorded By", payment.recorded_by.get_username()),
        ]
        headers = ["Description", "Amount"]
        rows = [["Payment received", f"{payment.amount:.2f}"]]
        totals = [
            ("Amount Paid", f"{payment.amount:.2f}"),
            ("Remaining Balance", f"{invoice.balance_due:.2f}"),
        ]

        pdf_bytes = render_simple_document(
            title="PAYMENT RECEIPT",
            subtitle=f"Receipt #{payment.receipt_number}",
            meta_pairs=meta,
            table_headers=headers,
            table_rows=rows,
            totals=totals,
            footer_note="This receipt confirms the payment above was recorded against the referenced invoice.",
        )
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="receipt-{payment.pk}.pdf"'
        return response


class PaymentsExportView(APIView):
    """GET /reports/payments/export?format=csv -- "Export Report" button."""
    permission_classes = [IsAdminOrAccountant]

    def get(self, request):
        payments = Payment.objects.select_related("invoice", "recorded_by").all()
        for key, value in request.query_params.items():
            if key in ("invoice", "method"):
                payments = payments.filter(**{key: value})

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="payments_export.csv"'
        writer = csv.writer(response)
        writer.writerow(["Receipt #", "Invoice #", "Amount", "Method", "Paid At", "Recorded By"])
        for p in payments:
            writer.writerow([
                p.receipt_number,
                p.invoice.invoice_number or f"DRAFT-{p.invoice_id}",
                p.amount, p.method, p.paid_at, p.recorded_by.get_username(),
            ])
        return response


class PaymentScheduleListView(generics.ListAPIView):
    """GET /payment-schedules?invoice_id= — list installments for an invoice."""
    queryset = PaymentSchedule.objects.select_related("invoice").all()
    serializer_class = PaymentScheduleSerializer
    permission_classes = [IsAdminOrAccountant]
    filterset_fields = ["invoice"]


class PaymentScheduleDetailUpdateView(generics.UpdateAPIView):
    """PATCH /payment-schedules/{id} — manual adjustment to a due date/amount."""
    queryset = PaymentSchedule.objects.all()
    serializer_class = PaymentScheduleSerializer
    permission_classes = [IsAdminOrAccountant]


_FREQUENCY_DAYS = {"WEEKLY": 7, "BIWEEKLY": 14, "MONTHLY": 30}


class GenerateScheduleView(APIView):
    """
    POST /sales-invoices/{id}/generate-schedule
    Body: {down_payment, installment_count, frequency}
    Creates PaymentSchedule rows for the remaining balance after the down
    payment, spread evenly across `installment_count` installments.
    """
    permission_classes = [IsAdminAgentOrAccountant]

    def post(self, request, pk):
        from sales.models import SalesInvoice
        import datetime

        invoice = generics.get_object_or_404(SalesInvoice, pk=pk)
        if invoice.status != "OPEN":
            return Response(
                {"error": {"code": "conflict", "message": "A payment schedule can only be generated for an OPEN invoice.", "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )
        if PaymentSchedule.objects.filter(invoice=invoice).exists():
            return Response(
                {"error": {"code": "conflict", "message": "A payment schedule already exists for this invoice.", "fields": {}}},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = GenerateScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        financed_amount = invoice.balance_due - data["down_payment"]
        if financed_amount <= 0:
            return Response(
                {"error": {"code": "bad_request", "message": "Down payment must be less than the outstanding balance.", "fields": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        count = data["installment_count"]
        step_days = _FREQUENCY_DAYS[data["frequency"]]
        per_installment = (financed_amount / count).quantize(invoice.balance_due)

        rows = []
        running_total = 0
        today = datetime.date.today()
        for i in range(1, count + 1):
            amount = per_installment
            if i == count:
                # last installment absorbs any rounding remainder
                amount = financed_amount - running_total
            running_total += amount
            rows.append(PaymentSchedule(
                invoice=invoice, installment_number=i,
                due_date=today + datetime.timedelta(days=step_days * i),
                amount_due=amount,
            ))
        PaymentSchedule.objects.bulk_create(rows)

        schedule = PaymentSchedule.objects.filter(invoice=invoice).order_by("installment_number")
        return Response(PaymentScheduleSerializer(schedule, many=True).data, status=status.HTTP_201_CREATED)


class FinancingAccountListCreateView(generics.ListCreateAPIView):
    """
    GET  /financing-accounts?invoice_id=   list financing agreements.
    POST /financing-accounts               basic capture. No amortization
                                            engine yet.
    """
    queryset = FinancingAccount.objects.select_related("invoice").all()
    serializer_class = FinancingAccountSerializer
    filterset_fields = ["invoice"]

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAdminOrAccountant()]
        return [IsAdminAgentOrAccountant()]


class FinancingAccountDetailView(generics.RetrieveUpdateAPIView):
    """
    GET   /financing-accounts/{id}   detail.
    PATCH /financing-accounts/{id}   update status (ACTIVE/PAID_OFF/DEFAULT).
    """
    queryset = FinancingAccount.objects.select_related("invoice").all()
    permission_classes = [IsAdminOrAccountant]

    def get_serializer_class(self):
        return FinancingAccountStatusUpdateSerializer if self.request.method == "PATCH" else FinancingAccountSerializer
