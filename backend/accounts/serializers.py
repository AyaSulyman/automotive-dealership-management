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


class UserCreateSerializer(serializers.Serializer):
    """Admin creates an employee: Django User + UserProfile in one step.

    `username` defaults to the email local part; `name` is shorthand for
    first_name. password optional — defaults to a known demo password so a
    freshly created account can be logged into immediately.
    """

    name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    username = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, required=False, default="changeme123")
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    role_id = serializers.IntegerField()
    branch_id = serializers.IntegerField(required=False, allow_null=True)
    is_active = serializers.BooleanField(default=True)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_role_id(self, value):
        if not Role.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Invalid role_id.")
        return value

    def validate_branch_id(self, value):
        if value is not None and not Branch.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Invalid branch_id.")
        return value

    def validate(self, attrs):
        first = attrs.get("name") or attrs.get("first_name", "")
        if not first:
            raise serializers.ValidationError("first_name (or name) is required.")
        attrs["first_name"] = first
        if not attrs.get("username"):
            attrs["username"] = attrs["email"].split("@")[0]
        return attrs

    def create(self, validated_data):
        username = validated_data.pop("username")
        email = validated_data.pop("email")
        password = validated_data.pop("password")
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name", "")
        is_active = validated_data.pop("is_active", True)
        phone = validated_data.pop("phone", "")
        role_id = validated_data.pop("role_id")
        branch_id = validated_data.pop("branch_id")

        user = User.objects.create(
            username=username, email=email, first_name=first_name,
            last_name=last_name, is_active=is_active,
        )
        user.set_password(password)
        user.save()

        profile, _ = UserProfile.objects.update_or_create(
            user=user,
            defaults={
                "role_id": role_id,
                "branch_id": branch_id,
                "phone": phone,
            },
        )
        return user


class UserUpdateSerializer(serializers.Serializer):
    """PATCH /users/{id} — same fields, all optional."""

    name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    email = serializers.EmailField(required=False)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True)
    role_id = serializers.IntegerField(required=False, allow_null=True)
    branch_id = serializers.IntegerField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)

    def validate_email(self, value):
        user = self.context.get("user")
        if User.objects.filter(email__iexact=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_role_id(self, value):
        if value is not None and not Role.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Invalid role_id.")
        return value

    def validate_branch_id(self, value):
        if value is not None and not Branch.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Invalid branch_id.")
        return value

    def update(self, user, validated_data):
        if "name" in validated_data and validated_data["name"]:
            user.first_name = validated_data.pop("name")
        for field in ("first_name", "last_name", "email", "is_active"):
            if field in validated_data:
                setattr(user, field, validated_data[field])
        if validated_data.get("password"):
            user.set_password(validated_data.pop("password"))
        user.save()

        defaults = {}
        for field in ("role_id", "branch_id", "phone"):
            if field in validated_data:
                defaults[field] = validated_data[field]
        if defaults:
            UserProfile.objects.update_or_create(user=user, defaults=defaults)
        return user