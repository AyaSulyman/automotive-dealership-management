"""
Person 1's core identity models: Role, Branch, and UserProfile.

Users themselves remain Django's built-in `auth.User` (AUTH_USER_MODEL is
NOT changed — Person 2's app migrations already reference the default model,
so swapping it now would break them). Roles, branches, phone, etc. live on a
OneToOne `UserProfile` instead. This is the model `common.permissions` reads
its role checks from (see the swap there).
"""
from django.conf import settings
from django.db import models


class Role(models.Model):
    """
    Named roles: admin, agent, accountant. Referenced by UserProfile.role and
    checked by common.permissions._user_roles().
    """

    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Branch(models.Model):
    """
    Dealership physical location. Vehicles and users belong to a branch.
    No dedicated API endpoints (not in the spec) — seeded directly.
    """

    name = models.CharField(max_length=120)
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    """
    Role + branch + phone for a Django user, 1:1. A user without a profile
    falls back to Django Groups in the permission checks (see
    common/permissions.py), so existing seeded users keep working.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.ForeignKey(
        Role, null=True, blank=True, on_delete=models.PROTECT,
        related_name="profiles",
    )
    branch = models.ForeignKey(
        Branch, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="profiles",
    )
    phone = models.CharField(max_length=30, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user.username} -> {self.role.name if self.role else '(no role)'}"