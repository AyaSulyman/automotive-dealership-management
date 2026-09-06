"""
Customer API endpoints (spec section 7):

    GET   /customers                    list (search/status filters, admin/agent)
    POST  /customers                    create (admin/agent)
    GET   /customers/{id}               detail (admin/agent)
    PATCH /customers/{id}               edit (admin/agent)
    GET   /customers/{id}/history       consolidated timeline across Person 2 data
    GET   /customers/{id}/balance       outstanding balance (admin/accountant)
    GET   /customers/{id}/statement     statement for a period (admin/accountant)

History/balance/statement read sales.SalesInvoice, sales.TradeIn and
payments.Payment through the loose `customer_id` integer those models carry.
Imports are lazy so this app stays resilient if Person 2's apps change.
"""
from datetime import date
from decimal import Decimal

from django.db.models import Q
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAdminOrAccountant, IsAdminOrAgent

from .models import Customer
from .serializers import CustomerSerializer


@extend_schema_view(
    get=extend_schema(tags=["Customers"], summary="List customers (?search=&status=)"),
    post=extend_schema(tags=["Customers"], summary="Create a customer"),
)
class CustomerListCreateView(generics.ListCreateAPIView):
    queryset = Customer.objects.select_related("created_by").order_by("-created_at")
    serializer_class = CustomerSerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAdminOrAgent()]
        return [IsAdminOrAgent()]

    def get_queryset(self):
        qs = Customer.objects.select_related("created_by").order_by("-created_at")
        params = self.request.query_params
        search = params.get("search")
        if search:
            qs = qs.filter(
                Q(first_name__icontains=search) | Q(last_name__icontains=search)
                | Q(email__icontains=search) | Q(phone__icontains=search)
                | Q(id_number__icontains=search)
            )
        cust_status = params.get("status")
        if cust_status:
            qs = qs.filter(status=cust_status)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = CustomerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = serializer.save(
            created_by=request.user if request.user.is_authenticated else None,
        )
        return Response(CustomerSerializer(customer).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(tags=["Customers"], summary="Customer detail"),
    patch=extend_schema(tags=["Customers"], summary="Edit a customer"),
)
class CustomerDetailView(generics.RetrieveUpdateAPIView):
    queryset = Customer.objects.select_related("created_by")
    serializer_class = CustomerSerializer

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAdminOrAgent()]
        return [IsAdminOrAgent()]


def _get_customer(pk):
    try:
        return Customer.objects.get(pk=pk)
    except Customer.DoesNotExist:
        raise NotFound(detail="Customer not found.")


@extend_schema_view(
    get=extend_schema(tags=["Customers"], summary="Customer consolidated history (invoices + payments + trade-ins)"),
)
class CustomerHistoryView(APIView):
    """GET /customers/{pk}/history — merged timeline across both people's data."""

    permission_classes = [IsAdminOrAgent]
    serializer_class = CustomerSerializer

    def get(self, request, pk):
        customer = _get_customer(pk)
        invoices, payments, trade_ins = [], [], []
        timeline = []

        try:
            from sales.models import SalesInvoice, TradeIn

            for inv in SalesInvoice.objects.filter(customer_id=customer.pk).order_by("sale_date"):
                row = {
                    "type": "invoice", "id": inv.pk, "date": str(inv.sale_date or ""),
                    "invoice_number": inv.invoice_number, "status": inv.status,
                    "total_amount": str(inv.total_amount), "balance_due": str(inv.balance_due),
                }
                invoices.append(row)
                timeline.append(row)
            for tr in TradeIn.objects.filter(customer_id=customer.pk).order_by("created_at"):
                row = {
                    "type": "trade_in", "id": tr.pk, "date": str(tr.created_at.date()),
                    "vin": tr.vin, "make": tr.make, "model": tr.model,
                    "year": tr.year, "appraised_value": str(tr.appraised_value),
                }
                trade_ins.append(row)
                timeline.append(row)
        except Exception:
            pass  # Person 2's sales app not present

        try:
            from payments.models import Payment

            for pay in Payment.objects.filter(invoice__customer_id=customer.pk).order_by("paid_at"):
                row = {
                    "type": "payment", "id": pay.pk, "date": str(pay.paid_at.date()),
                    "receipt_number": pay.receipt_number, "method": pay.method,
                    "amount": str(pay.amount),
                }
                payments.append(row)
                timeline.append(row)
        except Exception:
            pass

        timeline.sort(key=lambda r: r["date"] or "", reverse=True)
        return Response(
            {
                "customer": CustomerSerializer(customer).data,
                "invoices": invoices,
                "payments": payments,
                "trade_ins": trade_ins,
                "timeline": timeline,
            }
        )


@extend_schema_view(
    get=extend_schema(tags=["Customers"], summary="Customer outstanding balance (sum of invoice balance_due)"),
)
class CustomerBalanceView(APIView):
    """GET /customers/{pk}/balance — admin/accountant only."""

    permission_classes = [IsAdminOrAccountant]
    serializer_class = CustomerSerializer

    def get(self, request, pk):
        customer = _get_customer(pk)
        balance = Decimal("0.00")
        open_invoices = 0
        try:
            from sales.models import SalesInvoice

            invoices = SalesInvoice.objects.filter(customer_id=customer.pk)
            for inv in invoices:
                if inv.balance_due > 0:
                    balance += inv.balance_due
                    open_invoices += 1
        except Exception:
            pass
        return Response(
            {
                "customer_id": customer.pk,
                "balance_due": str(balance),
                "open_invoices": open_invoices,
            }
        )


@extend_schema_view(
    get=extend_schema(tags=["Customers"], summary="Generate a customer statement (?period_start=&period_end=)"),
)
class CustomerStatementView(APIView):
    """GET /customers/{pk}/statement — persists a payments.Statement summary."""

    permission_classes = [IsAdminOrAccountant]
    serializer_class = CustomerSerializer

    def get(self, request, pk):
        customer = _get_customer(pk)
        params = request.query_params
        try:
            start = date.fromisoformat(params.get("period_start"))
            end = date.fromisoformat(params.get("period_end"))
        except (TypeError, ValueError):
            return Response(
                {"error": {"code": "bad_request",
                           "message": "period_start and period_end are required (YYYY-MM-DD).",
                           "fields": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        summary = {
            "customer_id": customer.pk,
            "period_start": str(start),
            "period_end": str(end),
            "invoices": [],
            "payments": [],
            "invoices_total": "0.00",
            "payments_total": "0.00",
            "outstanding_balance": "0.00",
            "invoice_count": 0,
            "payment_count": 0,
        }
        invoices_total = Decimal("0.00")
        payments_total = Decimal("0.00")

        try:
            from sales.models import SalesInvoice

            invs = SalesInvoice.objects.filter(
                customer_id=customer.pk, sale_date__range=(start, end),
            )
            for inv in invs:
                invoices_total += inv.total_amount or 0
                summary["invoices"].append({
                    "id": inv.pk, "invoice_number": inv.invoice_number,
                    "sale_date": str(inv.sale_date), "total_amount": str(inv.total_amount),
                    "balance_due": str(inv.balance_due),
                })
        except Exception:
            pass

        try:
            from payments.models import Payment

            pays = Payment.objects.filter(
                invoice__customer_id=customer.pk, paid_at__date__range=(start, end),
            )
            for pay in pays:
                payments_total += pay.amount
                summary["payments"].append({
                    "id": pay.pk, "receipt_number": pay.receipt_number,
                    "paid_at": str(pay.paid_at), "amount": str(pay.amount), "method": pay.method,
                })
        except Exception:
            pass

        summary["invoice_count"] = len(summary["invoices"])
        summary["payment_count"] = len(summary["payments"])
        summary["invoices_total"] = str(invoices_total)
        summary["payments_total"] = str(payments_total)
        summary["outstanding_balance"] = str(invoices_total - payments_total)

        statement = None
        try:
            from payments.models import Statement

            statement = Statement.objects.create(
                customer_id=customer.pk, period_start=start, period_end=end,
                summary=summary,
            )
        except Exception:
            pass

        return Response(
            {
                "customer": CustomerSerializer(customer).data,
                "statement": summary,
                "generated_at": str(statement.generated_at) if statement else "",
            }
        )
