"""Serializer for Person 1's inventory domain."""
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

    def get_appraised_by(self, obj):
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
        if Vehicle.objects.filter(vin__iexact=value).exists():
            raise serializers.ValidationError("A vehicle with this VIN already exists.")
        return value.upper()

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
    class Meta:
        model = Document
        fields = [
            "id", "related_type", "related_id", "doc_type",
            "file", "original_filename", "uploaded_by", "created_at",
        ]
        read_only_fields = ["id", "original_filename", "uploaded_by", "created_at"]