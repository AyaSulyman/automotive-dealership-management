"""Serializer for Person 1's inventory domain."""
from rest_framework import serializers

from .models import Vendor


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = [
            "id", "name", "contact_person", "email", "phone",
            "address", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]