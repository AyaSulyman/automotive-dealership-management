from rest_framework import serializers

from .models import Payment, PaymentSchedule, FinancingAccount, Statement


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id", "invoice", "financing_account", "amount", "method",
            "reference_number", "receipt_number", "notes", "paid_at",
            "recorded_by", "created_at",
        ]
        read_only_fields = ["receipt_number", "recorded_by", "created_at"]


class PaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["invoice", "financing_account", "amount", "method", "reference_number", "notes", "paid_at"]

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


class FinancingAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancingAccount
        fields = [
            "id", "invoice", "lender_name", "down_payment", "term_months",
            "interest_rate", "monthly_payment", "status", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_invoice(self, value):
        if FinancingAccount.objects.filter(invoice=value).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise serializers.ValidationError("This invoice already has a financing account.")
        return value


class FinancingAccountStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancingAccount
        fields = ["status"]


class StatementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Statement
        fields = ["id", "customer_id", "period_start", "period_end", "summary", "generated_at"]
        read_only_fields = ["summary", "generated_at"]


class StatementGenerateSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    period_start = serializers.DateField()
    period_end = serializers.DateField()

    def validate(self, attrs):
        if attrs["period_end"] < attrs["period_start"]:
            raise serializers.ValidationError({"period_end": "Must be on or after period_start."})
        return attrs
