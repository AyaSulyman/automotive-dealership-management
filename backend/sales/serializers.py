from rest_framework import serializers

from .models import Discount, SalesInvoice, TaxRule, TradeIn


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
        if not SalesInvoice.objects.filter(pk=value).exists():
            raise serializers.ValidationError("No sales invoice with that id exists.")
        return value


class TaxRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxRule
        fields = ["id", "jurisdiction", "rate", "applies_to", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]


class DiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Discount
        fields = ["id", "invoice", "discount_type", "amount", "reason", "approved_by", "created_at"]
        read_only_fields = ["invoice", "approved_by", "created_at"]


class DiscountCreateSerializer(serializers.Serializer):
    discount_type = serializers.ChoiceField(choices=Discount.DISCOUNT_TYPE_CHOICES)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class SalesInvoiceSerializer(serializers.ModelSerializer):
    trade_ins = TradeInSerializer(many=True, read_only=True)
    discounts = DiscountSerializer(many=True, read_only=True)

    class Meta:
        model = SalesInvoice
        fields = [
            "id", "invoice_number", "customer_id", "vehicle_id", "branch_id",
            "salesperson", "sale_date", "status", "selling_price", "subtotal",
            "discount_amount", "tax_amount", "trade_in_credit", "total_amount",
            "balance_due", "trade_ins", "discounts", "created_at", "updated_at",
        ]
        read_only_fields = [
            "invoice_number", "status", "subtotal", "discount_amount", "tax_amount",
            "trade_in_credit", "total_amount", "balance_due", "created_at", "updated_at",
        ]


class SalesInvoiceCreateSerializer(serializers.ModelSerializer):
    """POST /sales-invoices — "Create Deal Worksheet" (status DRAFT)."""
    dealer_markup_discount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=0,
        help_text="Initial discount applied at deal creation.",
    )

    class Meta:
        model = SalesInvoice
        fields = ["customer_id", "vehicle_id", "salesperson", "branch_id", "selling_price", "dealer_markup_discount"]

    def create(self, validated_data):
        discount = validated_data.pop("dealer_markup_discount", 0)
        invoice = SalesInvoice(status="DRAFT", discount_amount=discount, **validated_data)
        invoice.save()
        return invoice


class SalesInvoiceUpdateSerializer(serializers.ModelSerializer):
    """PATCH /sales-invoices/{id} — only while status == DRAFT."""

    class Meta:
        model = SalesInvoice
        fields = ["customer_id", "vehicle_id", "salesperson", "branch_id", "selling_price", "discount_amount", "sale_date"]

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)
