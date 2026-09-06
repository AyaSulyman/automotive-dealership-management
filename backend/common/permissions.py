"""
Role-based permissions for the ADMS API (all apps).

Roles are read from Person 1's `accounts.UserProfile` model when one exists
(profile.role.name), and fall back to Django's built-in `auth.Group` names
otherwise so older seeded users keep working. `is_superuser` always passes
every role check.
"""
from rest_framework.permissions import BasePermission


def _user_roles(user):
    if not user or not user.is_authenticated or not user.is_active:
        return set()
    if user.is_superuser:
        return {"admin", "agent", "accountant"}
    try:
        role = user.profile.role
        if role is not None:
            return {role.name}
    except Exception:
        pass  # UserProfile missing or accounts app not migrated yet
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
