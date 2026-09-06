from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from .models import Payment, PaymentSchedule, FinancingAccount, Statement
from sales.serializers import customer_name_for, vehicle_data_for


class PaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    customer_name = serializers.SerializerMethodField()
    vehicle_name = serializers.SerializerMethodField()
    vin = serializers.SerializerMethodField()
    recorded_by_name = serializers.SerializerMethodField()
    balance_after = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id", "invoice", "invoice_number", "customer_name",
            "vehicle_name", "vin", "financing_account", "amount", "method",
            "reference_number", "receipt_number", "notes", "paid_at",
            "recorded_by", "recorded_by_name", "balance_after", "created_at",
        ]
        read_only_fields = ["receipt_number", "recorded_by", "created_at"]

    def get_customer_name(self, obj) -> str:
        return customer_name_for(obj.invoice.customer_id)

    def get_vehicle_name(self, obj) -> str:
        return vehicle_data_for(obj.invoice.vehicle_id)["name"]

    def get_vin(self, obj) -> str:
        return vehicle_data_for(obj.invoice.vehicle_id)["vin"]

    def get_recorded_by_name(self, obj) -> str:
        return obj.recorded_by.get_full_name().strip() or obj.recorded_by.get_username()

    def get_balance_after(self, obj) -> Decimal:
        paid = Payment.objects.filter(
            invoice_id=obj.invoice_id, created_at__lte=obj.created_at,
        ).aggregate(total=Sum("amount"))["total"] or 0
        return max(obj.invoice.total_amount - paid, 0)


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
        if invoice.status != "OPEN":
            raise serializers.ValidationError(
                {"invoice": "Payments can only be recorded against an OPEN invoice."}
            )
        if attrs["amount"] > invoice.balance_due:
            raise serializers.ValidationError(
                {"amount": f"Amount exceeds the outstanding balance ({invoice.balance_due})."}
            )
        financing = attrs.get("financing_account")
        if financing and financing.invoice_id != invoice.pk:
            raise serializers.ValidationError(
                {"financing_account": "This financing account belongs to a different invoice."}
            )
        return attrs


class PaymentScheduleSerializer(serializers.ModelSerializer):
    remaining = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = PaymentSchedule
        fields = [
            "id", "invoice", "invoice_number", "installment_number",
            "due_date", "amount_due", "amount_paid", "status", "remaining",
        ]
        read_only_fields = ["invoice", "installment_number", "amount_paid"]


class GenerateScheduleSerializer(serializers.Serializer):
    down_payment = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=0, min_value=0)
    installment_count = serializers.IntegerField(min_value=1, max_value=120)
    frequency = serializers.ChoiceField(choices=["WEEKLY", "BIWEEKLY", "MONTHLY"], default="MONTHLY")


class FinancingAccountSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)

    class Meta:
        model = FinancingAccount
        fields = [
            "id", "invoice", "invoice_number", "lender_name", "down_payment", "term_months",
            "interest_rate", "monthly_payment", "status", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_invoice(self, value):
        if value.status != "OPEN":
            raise serializers.ValidationError("Financing can only be created for an OPEN invoice.")
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
        from customers.models import Customer
        if not Customer.objects.filter(pk=attrs["customer_id"]).exists():
            raise serializers.ValidationError({"customer_id": "Customer not found."})
        if attrs["period_end"] < attrs["period_start"]:
            raise serializers.ValidationError({"period_end": "Must be on or after period_start."})
        return attrs
