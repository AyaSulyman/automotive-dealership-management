"""
Role-based permissions for Person 2's endpoints (sales, payments, reports).

INTEGRATION NOTE:
Person 1 owns Users & Roles (see API spec §2) but that app hasn't landed
yet. Rather than block Person 2's work on it, roles are checked against
Django's built-in `auth.Group` model — create groups named "admin",
"agent", "accountant" and assign users to them. `is_superuser` always
passes, so `admin` can just be Django's own superuser flag if preferred.

Once Person 1's dedicated Role/Profile model is merged, swap the lookup
inside `_user_roles()` to read from it instead of Groups — every call site
using `HasRole(...)` stays the same.
"""
from rest_framework.permissions import BasePermission


def _user_roles(user):
    if not user or not user.is_authenticated:
        return set()
    if user.is_superuser:
        return {"admin", "agent", "accountant"}
    return set(user.groups.values_list("name", flat=True))


class HasRole(BasePermission):
    """Base class — use the named subclasses below in `permission_classes`,
    or `roles_required("admin", "agent")` to build a one-off class."""

    roles = set()

    def has_permission(self, request, view):
        return bool(_user_roles(request.user) & set(self.roles))


def roles_required(*roles):
    """Factory: returns a permission class for an arbitrary role set.
    Usage: permission_classes = [roles_required("admin", "agent")]"""
    return type("DynamicHasRole", (HasRole,), {"roles": set(roles)})


def has_role(user, *roles):
    """Plain-function variant for use inside view logic / serializers."""
    return bool(_user_roles(user) & set(roles))


class IsAdmin(HasRole):
    roles = {"admin"}


class IsAdminOrAccountant(HasRole):
    roles = {"admin", "accountant"}


class IsAdminOrAgent(HasRole):
    roles = {"admin", "agent"}


class IsAdminAgentOrAccountant(HasRole):
    roles = {"admin", "agent", "accountant"}
