from django.db import models
from django.utils import timezone
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.models import Payment
from sales.models import SalesInvoice

from .integrations import get_inventory_snapshot
from .serializers import RecentInvoiceSerializer, RecentPaymentSerializer


class DashboardOverviewView(APIView):
    """
    GET /dashboard/overview
    Aggregate KPI cards. total_vehicles / status_breakdown are null until
    Person 1's inventory app lands (see reports/integrations.py) -- every
    other figure here is fully computed from Person 2's own data.
    """

    def get(self, request):
        year_start = timezone.now().replace(month=1, day=1).date()
        today = timezone.now().date()

        invoices_ytd = SalesInvoice.objects.filter(
            sale_date__gte=year_start, sale_date__lte=today,
        ).exclude(status="CANCELLED")
        payments_ytd = Payment.objects.filter(paid_at__date__gte=year_start, paid_at__date__lte=today)

        sales_total_ytd = invoices_ytd.aggregate(total=models.Sum("total_amount"))["total"] or 0
        payments_total_ytd = payments_ytd.aggregate(total=models.Sum("amount"))["total"] or 0
        outstanding_balance = SalesInvoice.objects.exclude(
            status__in=["CANCELLED", "DRAFT"],
        ).aggregate(total=models.Sum("balance_due"))["total"] or 0
        active_customer_count = SalesInvoice.objects.exclude(
            status="CANCELLED",
        ).values("customer_id").distinct().count()

        payload = {
            "sales_invoice_total_ytd": str(sales_total_ytd),
            "payments_received_ytd": str(payments_total_ytd),
            "outstanding_balance": str(outstanding_balance),
            "active_customer_count": active_customer_count,
            "invoice_count_ytd": invoices_ytd.count(),
        }
        payload.update(get_inventory_snapshot())
        return Response(payload)


class RecentInvoicesView(ListAPIView):
    """GET /dashboard/recent-invoices?limit=5"""
    serializer_class = RecentInvoiceSerializer

    def get_queryset(self):
        limit = int(self.request.query_params.get("limit", 5))
        return SalesInvoice.objects.exclude(status="CANCELLED").order_by("-created_at")[:limit]

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response(serializer.data)


class RecentPaymentsView(ListAPIView):
    """GET /dashboard/recent-payments?limit=5"""
    serializer_class = RecentPaymentSerializer

    def get_queryset(self):
        limit = int(self.request.query_params.get("limit", 5))
        return Payment.objects.select_related("invoice").order_by("-paid_at")[:limit]

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response(serializer.data)
