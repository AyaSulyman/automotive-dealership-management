from rest_framework import serializers

from .models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    created_by = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            "id", "first_name", "last_name", "full_name", "email", "phone", "alternate_phone",
            "address", "city", "state", "zip_code", "id_type", "id_number",
            "date_of_birth", "status", "notes", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_created_by(self, obj) -> str | None:
        return obj.created_by.username if obj.created_by else None

    def get_full_name(self, obj) -> str:
        return f"{obj.first_name} {obj.last_name}".strip()
