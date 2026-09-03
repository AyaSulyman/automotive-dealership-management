from django.db import models
from django.utils import timezone
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAdminOrAccountant
from payments.models import Payment
from sales.models import SalesInvoice

from .integrations import get_inventory_snapshot, get_inventory_cost_basis_split, get_work_order_costs_mtd, get_vehicle_cost_basis
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


class FinanceOverviewView(APIView):
    """
    GET /reports/finance/overview
    "Overview" tab: Total Sales MTD, Payments Received (MTD), Outstanding
    Balance, Current Inventory Cost Basis (New/Used split), Work Order
    Costs MTD. The last two are inventory/reconditioning figures Person 2
    doesn't own the data for -- null until Person 1's catalog app lands.
    """
    permission_classes = [IsAdminOrAccountant]

    def get(self, request):
        month_start = timezone.now().replace(day=1).date()
        today = timezone.now().date()

        sales_mtd = SalesInvoice.objects.filter(
            sale_date__gte=month_start, sale_date__lte=today,
        ).exclude(status="CANCELLED").aggregate(total=models.Sum("total_amount"))["total"] or 0

        payments_mtd = Payment.objects.filter(
            paid_at__date__gte=month_start, paid_at__date__lte=today,
        ).aggregate(total=models.Sum("amount"))["total"] or 0

        outstanding_balance = SalesInvoice.objects.exclude(
            status__in=["CANCELLED", "DRAFT"],
        ).aggregate(total=models.Sum("balance_due"))["total"] or 0

        payload = {
            "total_sales_mtd": str(sales_mtd),
            "payments_received_mtd": str(payments_mtd),
            "outstanding_balance": str(outstanding_balance),
            "work_order_costs_mtd": get_work_order_costs_mtd(),
        }
        payload.update(get_inventory_cost_basis_split())
        return Response(payload)


class VehicleFinancialSummaryView(APIView):
    """
    GET /reports/vehicle-financial-summary?vehicle_id=
    Per-vehicle cost basis vs. sale price (ACC-01). cost_basis is null
    until Person 1's catalog app lands; everything sale-side (price,
    margin against what we know) is fully computed.
    """
    permission_classes = [IsAdminOrAccountant]

    def get(self, request):
        vehicle_id = request.query_params.get("vehicle_id")
        if not vehicle_id:
            return Response(
                {"error": {"code": "bad_request", "message": "vehicle_id is required.", "fields": {}}},
                status=400,
            )

        invoice = SalesInvoice.objects.filter(vehicle_id=vehicle_id).exclude(status="CANCELLED").order_by("-created_at").first()
        cost_basis = get_vehicle_cost_basis(vehicle_id)

        sale_price = str(invoice.total_amount) if invoice else None
        gross_profit = None
        if invoice and cost_basis is not None:
            gross_profit = str(invoice.total_amount - cost_basis)

        return Response({
            "vehicle_id": int(vehicle_id),
            "invoice_id": invoice.id if invoice else None,
            "invoice_status": invoice.status if invoice else None,
            "sale_price": sale_price,
            "cost_basis": str(cost_basis) if cost_basis is not None else None,
            "gross_profit": gross_profit,
        })
