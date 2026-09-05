"""
Person 1's inventory domain models. Each feature branch lands its models
here:

    feature/vendors         -> Vendor
    feature/purchase-orders -> PurchaseOrder
    feature/vehicles        -> Vehicle, VehicleMedia, VehicleValuation
    feature/documents       -> Document

Person 1 owns Vendors / Purchase Orders / Vehicles / Documents (spec
sections 3-6).
"""
from django.conf import settings
from django.db import models


class Vendor(models.Model):
    """
    A vehicle supplier (API spec section 3). Referenced by PurchaseOrder.
    Delete is a soft delete (is_active -> False), admin-only.
    """

    name = models.CharField(max_length=150)
    contact_person = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name