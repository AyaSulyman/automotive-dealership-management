"""Transactional deal worksheet for the server-rendered sales screens."""
from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.generics import get_object_or_404, ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from common.permissions import IsAdminOrAccountant
from customers.models import Customer
from inventory.models import Vehicle
from reports.audit import log_action
from .models import Discount, SalesInvoice, TaxRule, TradeIn
from .serializers import SalesInvoiceSerializer


def tax_rate():
    rule = TaxRule.objects.filter(is_active=True).order_by("id").first()
    return rule.rate if rule else Decimal("0.00")


def validate_vehicle(vehicle, invoice=None):
    own_reservation = invoice and invoice.vehicle_id == vehicle.pk and vehicle.status == "RESERVED"
    if vehicle.status not in {"AVAILABLE", "IN_STOCK"} and not own_reservation:
        raise serializers.ValidationError({"vehicle_id": "This vehicle is not available for sale."})
    sold = SalesInvoice.objects.filter(vehicle_id=vehicle.pk, status__in=["OPEN", "PAID"])
    if invoice:
        sold = sold.exclude(pk=invoice.pk)
    if sold.exists():
        raise serializers.ValidationError({"vehicle_id": "This vehicle already has a finalized invoice."})


def finalize_invoice(invoice, user):
    """Caller holds the invoice lock; serialize finalization of one vehicle."""
    if invoice.status != "DRAFT":
        raise serializers.ValidationError("Only a draft deal can be finalized.")
    vehicle = get_object_or_404(Vehicle.objects.select_for_update(), pk=invoice.vehicle_id)
    validate_vehicle(vehicle, invoice)
    if not Customer.objects.filter(pk=invoice.customer_id).exclude(status="INACTIVE").exists():
        raise serializers.ValidationError({"customer_id": "Select an active customer."})
    invoice.recompute_totals(tax_rate=tax_rate())
    if invoice.total_amount <= 0:
        raise serializers.ValidationError("The invoice total must be greater than zero.")
    invoice.invoice_number = f"INV-{timezone.now().year}-{invoice.pk:06d}"
    invoice.sale_date = timezone.localdate()
    invoice.status = "OPEN"
    invoice.save()
    vehicle.status = "SOLD"
    vehicle.save(update_fields=["status", "updated_at"])
    log_action(user, "UPDATE", "SalesInvoice", invoice.pk, {"status": "OPEN"})


class CustomerOptionSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    class Meta:
        model = Customer
        fields = ["id", "name"]
    def get_name(self, obj) -> str:
        return str(obj)


class VehicleOptionSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    class Meta:
        model = Vehicle
        fields = ["id", "name", "vin", "selling_price"]
    def get_name(self, obj) -> str:
        return f"{obj.year} {obj.make} {obj.model}"


class CustomerOptionsView(ListAPIView):
    permission_classes = [IsAdminOrAccountant]
    serializer_class = CustomerOptionSerializer
    def get_queryset(self):
        qs = Customer.objects.exclude(status="INACTIVE").order_by("first_name", "id")
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(Q(first_name__icontains=search) | Q(last_name__icontains=search))
        return qs


class VehicleOptionsView(ListAPIView):
    permission_classes = [IsAdminOrAccountant]
    serializer_class = VehicleOptionSerializer
    def get_queryset(self):
        qs = Vehicle.objects.filter(status__in=["AVAILABLE", "IN_STOCK"]).exclude(
            pk__in=SalesInvoice.objects.filter(status__in=["DRAFT", "OPEN", "PAID"]).values("vehicle_id"))
        invoice_id = self.request.query_params.get("invoice_id", "")
        if invoice_id.isdigit():
            ids = SalesInvoice.objects.filter(pk=invoice_id, status="DRAFT").values("vehicle_id")
            qs = qs | Vehicle.objects.filter(pk__in=ids, status="RESERVED")
        return qs.order_by("make", "model", "id")


class DealWorksheetSerializer(serializers.Serializer):
    invoice_id = serializers.IntegerField(required=False, min_value=1)
    action = serializers.ChoiceField(choices=["quote", "draft", "finalize"])
    customer_id = serializers.IntegerField(min_value=1)
    vehicle_id = serializers.IntegerField(min_value=1)
    selling_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, default=0)
    trade_in_value = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, default=0)
    trade_in_details = serializers.CharField(max_length=2000, allow_blank=True, default="")

    def validate(self, data):
        if not Customer.objects.filter(pk=data["customer_id"]).exclude(status="INACTIVE").exists():
            raise serializers.ValidationError({"customer_id": "Select an active customer."})
        if data["discount_amount"] > data["selling_price"]:
            raise serializers.ValidationError({"discount_amount": "Discount cannot exceed the selling price."})
        if bool(data["trade_in_value"]) != bool(data["trade_in_details"].strip()):
            raise serializers.ValidationError({"trade_in_details": "Enter both the trade-in details and a positive appraisal value."})
        return data


class DealWorksheetView(APIView):
    permission_classes = [IsAdminOrAccountant]

    @extend_schema(request=DealWorksheetSerializer, responses=SalesInvoiceSerializer, tags=["Sales Invoices"])
    @transaction.atomic
    def post(self, request):
        form = DealWorksheetSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        invoice = None
        if data.get("invoice_id"):
            invoice = get_object_or_404(SalesInvoice.objects.select_for_update(), pk=data["invoice_id"])
            if invoice.status != "DRAFT":
                raise serializers.ValidationError("A finalized or cancelled invoice cannot be edited.")
        previous_vehicle_id = invoice.vehicle_id if invoice else None
        vehicle = get_object_or_404(Vehicle.objects.select_for_update(), pk=data["vehicle_id"])
        validate_vehicle(vehicle, invoice)
        customer = Customer.objects.get(pk=data["customer_id"])
        if invoice and invoice.trade_ins.count() > 1:
            raise serializers.ValidationError(
                "This draft has multiple trade-ins. Use the individual trade-in API to edit it.")
        created = invoice is None
        invoice = invoice or SalesInvoice(salesperson=request.user)
        invoice.customer_id, invoice.vehicle_id = customer.pk, vehicle.pk
        invoice.selling_price = data["selling_price"]
        invoice.discount_amount = data["discount_amount"]
        invoice.trade_in_credit = data["trade_in_value"]
        invoice.recompute_totals(tax_rate=tax_rate())
        if invoice.total_amount <= 0:
            raise serializers.ValidationError({"trade_in_value": "Discount and trade-in credit must leave a positive total."})
        if data["action"] == "quote":
            return Response({
                "customer_name": str(customer),
                "vehicle_name": f"{vehicle.year} {vehicle.make} {vehicle.model}",
                **{field: str(getattr(invoice, field)) for field in (
                    "selling_price", "discount_amount", "tax_amount", "trade_in_credit", "total_amount", "balance_due")},
                "tax_rate": str(tax_rate()),
            })
        invoice.save()
        if previous_vehicle_id and previous_vehicle_id != vehicle.pk:
            previous = Vehicle.objects.select_for_update().filter(pk=previous_vehicle_id, status="RESERVED").first()
            if previous and not SalesInvoice.objects.filter(
                vehicle_id=previous.pk, status="DRAFT",
            ).exclude(pk=invoice.pk).exists():
                previous.status = "AVAILABLE"
                previous.save(update_fields=["status", "updated_at"])
        if data["action"] == "draft" and vehicle.status != "RESERVED":
            vehicle.status = "RESERVED"
            vehicle.save(update_fields=["status", "updated_at"])
        invoice.discounts.all().delete()
        if invoice.discount_amount:
            Discount.objects.create(invoice=invoice, discount_type="FIXED",
                                    amount=invoice.discount_amount, reason="Deal worksheet discount")
        trade_in = invoice.trade_ins.first()
        if data["trade_in_value"]:
            trade_in = trade_in or TradeIn(credited_invoice=invoice, appraised_by=request.user)
            trade_in.customer_id = customer.pk
            trade_in.condition_notes = data["trade_in_details"]
            trade_in.appraised_value = data["trade_in_value"]
            trade_in.save()
            if not trade_in.credited_reference:
                trade_in.credited_reference = f"TRD-{trade_in.pk:06d}"
                trade_in.save(update_fields=["credited_reference"])
        elif trade_in:
            trade_in.credited_invoice = None
            trade_in.credited_reference = ""
            trade_in.save(update_fields=["credited_invoice", "credited_reference", "updated_at"])
        if data["action"] == "finalize":
            finalize_invoice(invoice, request.user)
        else:
            log_action(request.user, "CREATE" if created else "UPDATE", "SalesInvoice", invoice.pk, {"status": invoice.status})
        return Response(SalesInvoiceSerializer(invoice).data, status=201 if created else 200)
