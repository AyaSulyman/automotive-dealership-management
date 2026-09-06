from rest_framework import serializers

from .models import Discount, SalesInvoice, TaxRule, TradeIn


def customer_name_for(customer_id):
    """Resolve a loose customer id without changing the existing schema."""
    try:
        from customers.models import Customer

        customer = Customer.objects.filter(pk=customer_id).only(
            "first_name", "last_name"
        ).first()
    except (ImportError, RuntimeError):
        customer = None
    if customer is None:
        return f"Customer #{customer_id}"
    return f"{customer.first_name} {customer.last_name}".strip()


def vehicle_data_for(vehicle_id):
    """Resolve display data for the invoice's loose vehicle id."""
    try:
        from inventory.models import Vehicle

        vehicle = Vehicle.objects.filter(pk=vehicle_id).only(
            "year", "make", "model", "vin"
        ).first()
    except (ImportError, RuntimeError):
        vehicle = None
    if vehicle is None:
        return {
            "name": f"Vehicle #{vehicle_id}",
            "vin": "",
        }
    return {
        "name": f"{vehicle.year} {vehicle.make} {vehicle.model}".strip(),
        "vin": vehicle.vin,
    }


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
    customer_name = serializers.SerializerMethodField()
    vehicle_name = serializers.SerializerMethodField()
    vin = serializers.SerializerMethodField()
    customer_details = serializers.SerializerMethodField()
    salesperson_name = serializers.SerializerMethodField()

    class Meta:
        model = SalesInvoice
        fields = [
            "id", "invoice_number", "customer_id", "customer_name",
            "vehicle_id", "vehicle_name", "vin", "branch_id",
            "customer_details", "salesperson_name", "salesperson", "sale_date", "status", "selling_price", "subtotal",
            "discount_amount", "tax_amount", "trade_in_credit", "total_amount",
            "balance_due", "trade_ins", "discounts", "created_at", "updated_at",
        ]
        read_only_fields = [
            "invoice_number", "status", "subtotal", "discount_amount", "tax_amount",
            "trade_in_credit", "total_amount", "balance_due", "created_at", "updated_at",
        ]

    def get_customer_details(self, obj) -> dict:
        from customers.models import Customer
        row = Customer.objects.filter(pk=obj.customer_id).values("email", "phone", "address").first()
        return row or {}

    def get_salesperson_name(self, obj) -> str:
        return obj.salesperson.get_full_name() or obj.salesperson.username

    def get_customer_name(self, obj) -> str:
        return customer_name_for(obj.customer_id)

    def get_vehicle_name(self, obj) -> str:
        return vehicle_data_for(obj.vehicle_id)["name"]

    def get_vin(self, obj) -> str:
        return vehicle_data_for(obj.vehicle_id)["vin"]


class SalesInvoiceCreateSerializer(serializers.ModelSerializer):
    """POST /sales-invoices — "Create Deal Worksheet" (status DRAFT)."""
    dealer_markup_discount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=0,
        help_text="Initial discount applied at deal creation.",
    )

    class Meta:
        model = SalesInvoice
        fields = ["customer_id", "vehicle_id", "selling_price", "dealer_markup_discount"]

    def validate_customer_id(self, value):
        from customers.models import Customer
        if not Customer.objects.filter(pk=value).exclude(status="INACTIVE").exists():
            raise serializers.ValidationError("Select an active customer.")
        return value

    def validate_vehicle_id(self, value):
        from inventory.models import Vehicle
        if not Vehicle.objects.filter(pk=value, status__in=["AVAILABLE", "IN_STOCK"]).exists():
            raise serializers.ValidationError("Select an available vehicle.")
        if SalesInvoice.objects.filter(vehicle_id=value, status__in=["DRAFT", "OPEN", "PAID"]).exists():
            raise serializers.ValidationError("This vehicle already belongs to an active deal.")
        return value

    def validate(self, attrs):
        if attrs.get("dealer_markup_discount", 0) > attrs["selling_price"]:
            raise serializers.ValidationError({"dealer_markup_discount": "Discount cannot exceed the selling price."})
        return attrs

    def create(self, validated_data):
        discount = validated_data.pop("dealer_markup_discount", 0)
        invoice = SalesInvoice(status="DRAFT", discount_amount=discount, **validated_data)
        invoice.save()
        return invoice


class SalesInvoiceUpdateSerializer(serializers.ModelSerializer):
    """PATCH /sales-invoices/{id} — only while status == DRAFT."""

    class Meta:
        model = SalesInvoice
        fields = ["customer_id", "vehicle_id", "selling_price", "discount_amount"]

    def validate_customer_id(self, value):
        from customers.models import Customer
        if not Customer.objects.filter(pk=value).exclude(status="INACTIVE").exists():
            raise serializers.ValidationError("Select an active customer.")
        return value

    def validate_vehicle_id(self, value):
        from inventory.models import Vehicle
        instance = self.instance
        own = instance and instance.vehicle_id == value
        allowed = ["AVAILABLE", "IN_STOCK"] + (["RESERVED"] if own else [])
        if not Vehicle.objects.filter(pk=value, status__in=allowed).exists():
            raise serializers.ValidationError("Select an available vehicle.")
        used = SalesInvoice.objects.filter(vehicle_id=value, status__in=["DRAFT", "OPEN", "PAID"])
        if instance:
            used = used.exclude(pk=instance.pk)
        if used.exists():
            raise serializers.ValidationError("This vehicle already belongs to an active deal.")
        return value

    def validate(self, attrs):
        price = attrs.get("selling_price", self.instance.selling_price)
        discount = attrs.get("discount_amount", self.instance.discount_amount)
        if discount > price:
            raise serializers.ValidationError({"discount_amount": "Discount cannot exceed the selling price."})
        return attrs

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)
