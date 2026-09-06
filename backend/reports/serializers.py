from rest_framework import serializers

from payments.models import Payment
from sales.models import SalesInvoice
from sales.serializers import customer_name_for, vehicle_data_for

from .models import AuditLog


class RecentInvoiceSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField()
    vehicle_name = serializers.SerializerMethodField()
    vin = serializers.SerializerMethodField()

    class Meta:
        model = SalesInvoice
        fields = [
            "id", "invoice_number", "customer_id", "customer_name",
            "vehicle_id", "vehicle_name", "vin", "status", "total_amount",
            "balance_due", "sale_date",
        ]

    def get_customer_name(self, obj) -> str:
        return customer_name_for(obj.customer_id)

    def get_vehicle_name(self, obj) -> str:
        return vehicle_data_for(obj.vehicle_id)["name"]

    def get_vin(self, obj) -> str:
        return vehicle_data_for(obj.vehicle_id)["vin"]


class RecentPaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    customer_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id", "receipt_number", "invoice", "invoice_number",
            "customer_name", "amount", "method", "paid_at",
        ]

    def get_customer_name(self, obj) -> str:
        return customer_name_for(obj.invoice.customer_id)


class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.get_username", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = ["id", "user", "username", "action", "entity_type", "entity_id", "changes", "created_at"]
