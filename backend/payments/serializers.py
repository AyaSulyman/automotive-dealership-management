from rest_framework import serializers

from .models import Payment, PaymentSchedule


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


class PaymentScheduleSerializer(serializers.ModelSerializer):
    remaining = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = PaymentSchedule
        fields = ["id", "invoice", "installment_number", "due_date", "amount_due", "amount_paid", "status", "remaining"]
        read_only_fields = ["invoice", "installment_number", "amount_paid"]


class GenerateScheduleSerializer(serializers.Serializer):
    down_payment = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0, min_value=0)
    installment_count = serializers.IntegerField(min_value=1, max_value=120)
    frequency = serializers.ChoiceField(choices=["WEEKLY", "BIWEEKLY", "MONTHLY"], default="MONTHLY")
