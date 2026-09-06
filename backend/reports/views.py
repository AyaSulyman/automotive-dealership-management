from decimal import Decimal

from django.db import models
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAdmin, IsAdminOrAccountant
from payments.models import Payment
from sales.models import SalesInvoice

from .integrations import (
    get_inventory_cost_basis_split,
    get_inventory_snapshot,
    get_vehicle_financial_data,
    get_work_order_costs_mtd,
)
from .models import AuditLog
from .serializers import AuditLogSerializer, RecentInvoiceSerializer, RecentPaymentSerializer


class DashboardOverviewView(APIView):
    permission_classes = [IsAdmin]

    """
    GET /dashboard/overview
    Aggregate dashboard KPI cards from the shared sales, payments, customer,
    and inventory data.
    """

    @extend_schema(tags=["Dashboard"], summary="Aggregate KPI overview", responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        year_start = timezone.now().replace(month=1, day=1).date()
        today = timezone.now().date()

        invoices_ytd = SalesInvoice.objects.filter(
            sale_date__gte=year_start, sale_date__lte=today,
        ).exclude(status__in=["CANCELLED", "DRAFT"])
        payments_ytd = Payment.objects.filter(paid_at__date__gte=year_start, paid_at__date__lte=today)

        sales_total_ytd = invoices_ytd.aggregate(total=models.Sum("total_amount"))["total"] or 0
        payments_total_ytd = payments_ytd.aggregate(total=models.Sum("amount"))["total"] or 0
        outstanding_balance = SalesInvoice.objects.exclude(
            status__in=["CANCELLED", "DRAFT"],
        ).aggregate(total=models.Sum("balance_due"))["total"] or 0
        try:
            from customers.models import Customer

            active_customer_count = Customer.objects.filter(
                status__in=["ACTIVE", "VIP"]
            ).count()
        except (ImportError, RuntimeError):
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


@extend_schema_view(get=extend_schema(tags=["Dashboard"], summary="Recent sales invoices"))
class RecentInvoicesView(ListAPIView):
    permission_classes = [IsAdmin]

    """GET /dashboard/recent-invoices?limit=5"""
    serializer_class = RecentInvoiceSerializer

    def get_queryset(self):
        limit = int(self.request.query_params.get("limit", 5))
        return SalesInvoice.objects.exclude(status__in=["CANCELLED", "DRAFT"]).order_by("-created_at")[:limit]

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response(serializer.data)


@extend_schema_view(get=extend_schema(tags=["Dashboard"], summary="Recent payments"))
class RecentPaymentsView(ListAPIView):
    permission_classes = [IsAdmin]

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
    Balance, Current Inventory Cost Basis (New/Used split), and recorded
    reconditioning costs for vehicles added this month.
    """
    permission_classes = [IsAdminOrAccountant]

    @extend_schema(tags=["Finance & Reports"], summary="Finance overview (Overview tab)", responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        month_start = timezone.now().replace(day=1).date()
        today = timezone.now().date()

        sales_mtd = SalesInvoice.objects.filter(
            sale_date__gte=month_start, sale_date__lte=today,
        ).exclude(status__in=["CANCELLED", "DRAFT"]).aggregate(total=models.Sum("total_amount"))["total"] or 0

        payments_mtd_queryset = Payment.objects.filter(
            paid_at__date__gte=month_start, paid_at__date__lte=today,
        )
        payments_mtd = payments_mtd_queryset.aggregate(
            total=models.Sum("amount")
        )["total"] or 0

        outstanding_balance = SalesInvoice.objects.exclude(
            status__in=["CANCELLED", "DRAFT"],
        ).aggregate(total=models.Sum("balance_due"))["total"] or 0

        payload = {
            "total_sales_mtd": str(sales_mtd),
            "payments_received_mtd": str(payments_mtd),
            "payment_transaction_count": payments_mtd_queryset.count(),
            "outstanding_balance": str(outstanding_balance),
            "work_order_costs_mtd": get_work_order_costs_mtd(),
        }
        payload.update(get_inventory_cost_basis_split())
        return Response(payload)


class VehicleFinancialSummaryView(APIView):
    """
    GET /reports/vehicle-financial-summary?vehicle_id=
    Per-vehicle cost basis vs. sale price (ACC-01), resolved by database id
    or VIN.
    """
    permission_classes = [IsAdminOrAccountant]

    @extend_schema(tags=["Finance & Reports"], summary="Per-vehicle cost basis vs. sale price", responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        vehicle_id = request.query_params.get("vehicle_id")
        if not vehicle_id:
            return Response(
                {"error": {"code": "bad_request", "message": "vehicle_id is required.", "fields": {}}},
                status=400,
            )

        vehicle = get_vehicle_financial_data(vehicle_id)
        if vehicle is None:
            return Response(
                {"error": {"code": "not_found", "message": "Vehicle not found.", "fields": {}}},
                status=404,
            )

        invoice = SalesInvoice.objects.filter(
            vehicle_id=vehicle["vehicle_id"]
        ).exclude(status__in=["CANCELLED", "DRAFT"]).order_by("-created_at").first()
        cost_basis = Decimal(vehicle["total_cost_basis"])

        sale_price = str(invoice.selling_price) if invoice else None
        gross_profit = None
        if invoice:
            gross_profit = str(invoice.selling_price - cost_basis)

        return Response({
            **vehicle,
            "invoice_id": invoice.id if invoice else None,
            "invoice_status": invoice.status if invoice else None,
            "sale_price": sale_price,
            "cost_basis": str(cost_basis),
            "gross_profit": gross_profit,
        })


@extend_schema_view(get=extend_schema(tags=["Audit Log"], summary="Query the audit trail (admin-only)"))
class AuditLogListView(ListAPIView):
    """
    GET /audit-log?entity_type=&entity_id=&user_id=&date_from=&date_to=
    Not surfaced in any of the 10 UI screens, but required by SEC-03
    (MVP) -- admin-only troubleshooting endpoint.
    """
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        qs = AuditLog.objects.all()
        params = self.request.query_params
        if params.get("entity_type"):
            qs = qs.filter(entity_type=params["entity_type"])
        if params.get("entity_id"):
            qs = qs.filter(entity_id=params["entity_id"])
        if params.get("user_id"):
            qs = qs.filter(user_id=params["user_id"])
        if params.get("date_from"):
            qs = qs.filter(created_at__date__gte=params["date_from"])
        if params.get("date_to"):
            qs = qs.filter(created_at__date__lte=params["date_to"])
        return qs
