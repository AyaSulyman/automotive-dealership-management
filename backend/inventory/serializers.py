"""Serializer for Person 1's inventory domain."""
from rest_framework import serializers

from .models import PurchaseOrder, Vendor


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