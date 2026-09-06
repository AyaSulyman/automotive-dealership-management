"""Serializer for Person 1's inventory domain."""
from pathlib import Path
from datetime import date
from rest_framework import serializers

from .models import Document, PurchaseOrder, Vehicle, VehicleMedia, VehicleValuation, Vendor


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = [
            "id", "name", "contact_person", "email", "phone",
            "address", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class PurchaseOrderCreateSerializer(serializers.ModelSerializer):
    vendor_id = serializers.IntegerField()

    class Meta:
        model = PurchaseOrder
        fields = ["vendor_id", "order_date", "expected_date", "notes"]

    def validate_vendor_id(self, value):
        if not Vendor.objects.filter(pk=value, is_active=True).exists():
            raise serializers.ValidationError("Invalid or inactive vendor_id.")
        return value

    def create(self, validated_data):
        return PurchaseOrder.objects.create(**validated_data)


class PurchaseOrderSerializer(serializers.ModelSerializer):
    vendor_id = serializers.IntegerField(source="vendor.id", read_only=True)
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "id", "po_number", "vendor_id", "vendor_name", "order_date",
            "expected_date", "status", "notes", "created_at", "updated_at",
        ]
        read_only_fields = ["po_number", "created_at", "updated_at"]


class VehicleMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehicleMedia
        fields = ["id", "vehicle_id", "file", "media_type", "caption", "uploaded_by", "created_at"]
        read_only_fields = ["id", "created_at"]


class VehicleValuationSerializer(serializers.ModelSerializer):
    appraised_by = serializers.SerializerMethodField()

    class Meta:
        model = VehicleValuation
        fields = ["id", "vehicle_id", "value", "source", "notes", "appraised_by", "created_at"]
        read_only_fields = ["id", "vehicle_id", "appraised_by", "created_at"]

    def get_appraised_by(self, obj) -> str | None:
        return obj.appraised_by.username if obj.appraised_by else None


class VehicleSerializer(serializers.ModelSerializer):
    """Read/output shape. total_cost_basis is always server-computed."""

    branch_name = serializers.CharField(source="branch.name", read_only=True, default=None)
    po_number = serializers.CharField(source="purchase_order.po_number", read_only=True, default=None)
    photo_count = serializers.IntegerField(source="media.count", read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            "id", "vin", "make", "model", "year", "trim", "condition", "status",
            "branch_id", "branch_name", "purchase_order_id", "po_number",
            "acquisition_cost", "transport_cost", "recon_cost", "total_cost_basis",
            "selling_price", "photo_count", "created_at", "updated_at",
        ]
        read_only_fields = ["total_cost_basis"]

    def update(self, instance, validated_data):
        # Recompute cost basis whenever any cost component changes.
        instance = super().update(instance, validated_data)
        if any(k in validated_data for k in
               ("acquisition_cost", "transport_cost", "recon_cost")):
            instance.compute_cost_basis()
            instance.save(update_fields=["total_cost_basis", "updated_at"])
        return instance

    def validate_vin(self, value):
        value = value.strip().upper()
        if len(value) != 17 or not value.isalnum():
            raise serializers.ValidationError(
                "VIN must contain exactly 17 letters and numbers."
            )
        existing = Vehicle.objects.filter(vin__iexact=value)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError(
                "A vehicle with this VIN already exists."
            )
        return value

    def validate(self, attrs):
        if self.instance and self.instance.status in {"RESERVED", "SOLD"}:
            raise serializers.ValidationError(
                "A reserved or sold vehicle cannot be edited from inventory."
            )
        status = attrs.get("status")
        if status in {"RESERVED", "SOLD"} and (
            not self.instance or self.instance.status != status
        ):
            raise serializers.ValidationError({"status": "Reserved and sold statuses are controlled by the sales workflow."})
        for field in ("acquisition_cost", "transport_cost", "recon_cost", "selling_price"):
            value = attrs.get(field)
            if value is not None and value < 0:
                raise serializers.ValidationError({field: "Amount cannot be negative."})
        year = attrs.get("year")
        if year is not None and not 1886 <= year <= date.today().year + 1:
            raise serializers.ValidationError({"year": "Enter a valid vehicle year."})
        return attrs


class VehicleCreateSerializer(serializers.ModelSerializer):
    branch_id = serializers.IntegerField(required=False, allow_null=True)
    purchase_order_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = Vehicle
        fields = [
            "vin", "make", "model", "year", "trim", "condition", "status",
            "branch_id", "purchase_order_id",
            "acquisition_cost", "transport_cost", "recon_cost", "selling_price",
        ]

    def validate_vin(self, value):
        value = value.strip().upper()
        if len(value) != 17 or not value.isalnum():
            raise serializers.ValidationError("VIN must contain exactly 17 letters and numbers.")
        if Vehicle.objects.filter(vin__iexact=value).exists():
            raise serializers.ValidationError("A vehicle with this VIN already exists.")
        return value.upper()

    def validate(self, attrs):
        if attrs.get("status") in {"RESERVED", "SOLD"}:
            raise serializers.ValidationError({"status": "Reserved and sold statuses are controlled by the sales workflow."})
        for field in ("acquisition_cost", "transport_cost", "recon_cost", "selling_price"):
            value = attrs.get(field)
            if value is not None and value < 0:
                raise serializers.ValidationError({field: "Amount cannot be negative."})
        year = attrs.get("year")
        if year is not None and not 1886 <= year <= date.today().year + 1:
            raise serializers.ValidationError({"year": "Enter a valid vehicle year."})
        return attrs

    def validate_purchase_order_id(self, value):
        if value is not None and not PurchaseOrder.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Invalid purchase_order_id.")
        return value

    def create(self, validated_data):
        vehicle = Vehicle(**validated_data)
        vehicle.compute_cost_basis()
        vehicle.save()
        return vehicle


class DocumentSerializer(serializers.ModelSerializer):
    download_path = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id", "related_type", "related_id", "doc_type",
            "file", "download_path", "original_filename", "uploaded_by",
            "uploaded_by_name", "created_at",
        ]
        read_only_fields = ["id", "original_filename", "uploaded_by", "created_at"]
        extra_kwargs = {"file": {"write_only": True}}

    def get_download_path(self, obj) -> str:
        return f"/documents/{obj.pk}/download"

    def get_uploaded_by_name(self, obj) -> str:
        if not obj.uploaded_by:
            return ""
        return obj.uploaded_by.get_full_name().strip() or obj.uploaded_by.get_username()

    def validate_file(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Files must be 10 MB or smaller.")
        extension = Path(value.name).suffix.lower()
        if extension not in {".pdf", ".png", ".jpg", ".jpeg"}:
            raise serializers.ValidationError("Upload a PDF, PNG, JPG, or JPEG file.")
        content_type = str(getattr(value, "content_type", "")).lower()
        if content_type and content_type not in {
            "application/pdf", "image/png", "image/jpeg", "application/octet-stream",
        }:
            raise serializers.ValidationError("The selected file type is not supported.")
        return value

    def validate(self, attrs):
        related_type = attrs.get("related_type", getattr(self.instance, "related_type", None))
        related_id = attrs.get("related_id", getattr(self.instance, "related_id", None))
        if not related_type or not related_id:
            return attrs
        if related_type == "VEHICLE":
            exists = Vehicle.objects.filter(pk=related_id).exists()
        elif related_type == "CUSTOMER":
            from customers.models import Customer
            exists = Customer.objects.filter(pk=related_id).exists()
        elif related_type == "INVOICE":
            from sales.models import SalesInvoice
            exists = SalesInvoice.objects.filter(pk=related_id).exists()
        else:
            exists = False
        if not exists:
            raise serializers.ValidationError({"related_id": "The related record does not exist."})
        return attrs
