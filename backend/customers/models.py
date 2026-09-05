"""
Person 1's Customer model (API spec section 7).

The history / balance / statement endpoints aggregate data that lives in
Person 2's apps (sales.SalesInvoice, sales.TradeIn, payments.Payment) via
the loose `customer_id` integer they already carry — same cross-app pattern
both sides use.
"""
from django.conf import settings
from django.db import models


class Customer(models.Model):
    STATUS_CHOICES = [
        ("LEAD", "Lead"),
        ("ACTIVE", "Active"),
        ("VIP", "VIP"),
        ("INACTIVE", "Inactive"),
    ]
    ID_TYPE_CHOICES = [
        ("DL", "Driver's License"),
        ("PASSPORT", "Passport"),
        ("NATIONAL_ID", "National ID"),
    ]

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    alternate_phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=40, blank=True)
    zip_code = models.CharField(max_length=15, blank=True)
    id_type = models.CharField(max_length=20, choices=ID_TYPE_CHOICES, blank=True)
    id_number = models.CharField(max_length=50, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_customers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"