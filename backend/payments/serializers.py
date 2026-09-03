from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id", "invoice", "financing_account_id", "amount", "method",
            "reference_number", "receipt_number", "notes", "paid_at",
            "recorded_by", "created_at",
        ]
        read_only_fields = ["receipt_number", "recorded_by", "created_at"]


class PaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["invoice", "financing_account_id", "amount", "method", "reference_number", "notes", "paid_at"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Payment amount must be greater than zero.")
        return value

    def validate(self, attrs):
        invoice = attrs["invoice"]
        if invoice.status not in ("OPEN", "PAID"):
            raise serializers.ValidationError(
                {"invoice": "Payments can only be recorded against an OPEN invoice."}
            )
        if attrs["amount"] > invoice.balance_due:
            raise serializers.ValidationError(
                {"amount": f"Amount exceeds the outstanding balance ({invoice.balance_due})."}
            )
        return attrs
