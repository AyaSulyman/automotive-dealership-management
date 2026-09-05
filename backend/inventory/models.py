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


class Vehicle(models.Model):
    """
    A unit of inventory (API spec section 5). `total_cost_basis` is computed
    server-side from acquisition + transport + recon costs and never sent in
    request bodies. `mark_vehicle_sold` (sales/integrations.py) flips a sold
    vehicle to SOLD when a deal is finalized.
    """

    STATUS_CHOICES = [
        ("IN_TRANSIT", "In Transit"),
        ("IN_STOCK", "In Stock"),
        ("AVAILABLE", "Available"),
        ("RESERVED", "Reserved"),
        ("SOLD", "Sold"),
    ]
    CONDITION_CHOICES = [
        ("NEW", "New"),
        ("USED", "Used"),
    ]

    vin = models.CharField(max_length=50, unique=True)
    make = models.CharField(max_length=60)
    model = models.CharField(max_length=60)
    year = models.PositiveIntegerField()
    trim = models.CharField(max_length=60, blank=True)
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES, default="USED")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="IN_STOCK")

    branch = models.ForeignKey(
        "accounts.Branch", null=True, blank=True, on_delete=models.SET_NULL, related_name="vehicles",
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder, null=True, blank=True, on_delete=models.SET_NULL, related_name="vehicles",
    )

    acquisition_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    transport_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    recon_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost_basis = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_vehicles", null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.year} {self.make} {self.model} ({self.vin})"

    def compute_cost_basis(self):
        self.total_cost_basis = (
            (self.acquisition_cost or 0) + (self.transport_cost or 0) + (self.recon_cost or 0)
        )
        return self.total_cost_basis


class VehicleMedia(models.Model):
    """Photo / video attached to a vehicle (API spec section 5)."""

    MEDIA_TYPE_CHOICES = [
        ("PHOTO", "Photo"),
        ("VIDEO", "Video"),
    ]

    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="media")
    file = models.FileField(upload_to="vehicle_media/%Y/%m/")
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default="PHOTO")
    caption = models.CharField(max_length=200, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="vehicle_uploads",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Media {self.media_type} for vehicle {self.vehicle_id}"


class VehicleValuation(models.Model):
    """Manual appraisal of a vehicle (API spec section 5)."""

    SOURCE_CHOICES = [
        ("MANUAL", "Manual"),
        ("THIRD_PARTY", "Third-party"),
    ]

    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name="valuations")
    value = models.DecimalField(max_digits=12, decimal_places=2)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="MANUAL")
    notes = models.TextField(blank=True)
    appraised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="vehicle_valuations",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Valuation ${self.value} for vehicle {self.vehicle_id}"


class Document(models.Model):
    """
    A generic file attachment (API spec section 6). related_type / related_id
    are loose references (VEHICLE/CUSTOMER/INVOICE) so one model serves all
    three domains — the same pattern Person 2 uses for its loose numeric IDs
    across apps.
    """

    RELATED_TYPE_CHOICES = [
        ("VEHICLE", "Vehicle"),
        ("CUSTOMER", "Customer"),
        ("INVOICE", "Invoice"),
    ]
    DOC_TYPE_CHOICES = [
        ("TITLE", "Title"),
        ("ID", "ID"),
        ("CONTRACT", "Contract"),
        ("INSPECTION", "Inspection"),
        ("BILL_OF_SALE", "Bill of Sale"),
    ]

    related_type = models.CharField(max_length=20, choices=RELATED_TYPE_CHOICES)
    related_id = models.IntegerField()
    doc_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES)
    file = models.FileField(upload_to="documents/%Y/%m/")
    original_filename = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="uploaded_documents",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.doc_type} for {self.related_type} #{self.related_id}"