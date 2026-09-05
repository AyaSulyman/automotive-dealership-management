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
from django.utils.crypto import get_random_string


def _po_number():
    return f"PO-{get_random_string(8).upper()}"


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


class PurchaseOrder(models.Model):
    """
    A stock order placed with a vendor (API spec section 4).

    Status lifecycle: PENDING -> RECEIVED -> CLOSED (forward only, enforced
    in the view). DELETE cancels the PO (status -> CANCELLED) but only when
    no vehicle has been received against it.
    """

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("RECEIVED", "Received"),
        ("CLOSED", "Closed"),
        ("CANCELLED", "Cancelled"),
    ]

    po_number = models.CharField(max_length=20, unique=True, default=_po_number, editable=False)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="purchase_orders")
    order_date = models.DateField()
    expected_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="purchase_orders", null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.po_number} ({self.vendor.name}, {self.status})"

    def has_received_vehicles(self):
        """Blocks cancellation once any vehicle came in off this PO."""
        try:
            from .models import Vehicle

            return Vehicle.objects.filter(
                purchase_order_id=self.pk, status__in=["IN_STOCK", "AVAILABLE", "RESERVED", "SOLD"],
            ).exists()
        except Exception:
            return False