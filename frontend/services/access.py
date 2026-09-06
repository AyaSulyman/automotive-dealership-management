"""Shared navigation targets and a fail-closed response for disallowed roles."""
from django.shortcuts import render
from django.urls import reverse
from .presenters import normalize_role, user_identity


def home_name(user):
    return {
        "admin": "dashboard",
        "agent": "inventory:inventory",
        "accountant": "inventory:deal-list",
    }.get(normalize_role(user.get("role")), "login-page")


def denied(request, user):
    return render(request, "access_denied.html", {
        "user_identity": user_identity(user),
        "home_url": reverse(home_name(user)),
    }, status=403)
