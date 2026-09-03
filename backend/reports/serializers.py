from rest_framework import serializers

from payments.models import Payment
from sales.models import SalesInvoice

from .models import AuditLog


class RecentInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesInvoice
        fields = ["id", "invoice_number", "customer_id", "vehicle_id", "status", "total_amount", "balance_due", "sale_date"]


class RecentPaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = Payment
        fields = ["id", "receipt_number", "invoice", "invoice_number", "amount", "method", "paid_at"]


class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.get_username", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = ["id", "user", "username", "action", "entity_type", "entity_id", "changes", "created_at"]
