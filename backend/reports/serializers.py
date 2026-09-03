from rest_framework import serializers

from payments.models import Payment
from sales.models import SalesInvoice


class RecentInvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalesInvoice
        fields = ["id", "invoice_number", "customer_id", "vehicle_id", "status", "total_amount", "balance_due", "sale_date"]


class RecentPaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = Payment
        fields = ["id", "receipt_number", "invoice", "invoice_number", "amount", "method", "paid_at"]
