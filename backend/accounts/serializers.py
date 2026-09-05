"""
Serializers for Person 1's identity domain (Authentication / Users & Roles).
"""
from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Branch, Role, UserProfile


def get_profile(user):
    """Safe accessor for a user's OneToOne profile (returns None if absent)."""
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        return None


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name", "description"]


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name", "address", "phone", "is_active"]


class UserDetailSerializer(serializers.ModelSerializer):
    """Shape returned by /auth/login and /auth/me: user + role + branch."""

    role = serializers.SerializerMethodField()
    branch = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name",
            "phone", "role", "branch", "is_active",
        ]
        read_only_fields = fields

    def get_role(self, user):
        profile = get_profile(user)
        if profile is not None and profile.role is not None:
            return profile.role.name
        groups = list(user.groups.values_list("name", flat=True))
        return groups[0] if groups else None

    def get_branch(self, user):
        profile = get_profile(user)
        if profile is not None and profile.branch is not None:
            return profile.branch.name
        return None

    def get_phone(self, user):
        profile = get_profile(user)
        return profile.phone if profile is not None else ""


class LoginRequestSerializer(serializers.Serializer):
    email = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class RefreshRequestSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(write_only=True)


class LogoutRequestSerializer(serializers.Serializer):
    refresh_token = serializers.CharField(write_only=True)


class TokenPairSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()


class LoginResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    user = UserDetailSerializer()


class UserProfileSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    branch = BranchSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = ["user", "phone", "role", "branch"]