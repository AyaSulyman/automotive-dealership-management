from rest_framework import serializers

from .models import TradeIn


class TradeInSerializer(serializers.ModelSerializer):
    is_credited = serializers.BooleanField(read_only=True)

    class Meta:
        model = TradeIn
        fields = [
            "id", "customer_id", "vin", "make", "model", "year", "mileage",
            "condition", "condition_notes", "appraised_value", "appraised_by",
            "credited_invoice_id", "credited_reference", "is_credited",
            "created_at", "updated_at",
        ]
        read_only_fields = ["credited_invoice_id", "credited_reference", "created_at", "updated_at"]


class ApplyCreditSerializer(serializers.Serializer):
    invoice_id = serializers.IntegerField()

    def validate_invoice_id(self, value):
        # Local import avoids a hard dependency on SalesInvoice existing
        # at import time for any code path that only needs TradeInSerializer.
        from .models import SalesInvoice
        if not SalesInvoice.objects.filter(pk=value).exists():
            raise serializers.ValidationError("No sales invoice with that id exists.")
        return value
