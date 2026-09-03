from django.conf import settings
from django.db import models


class TradeIn(models.Model):
    """
    Trade-in appraisal captured during the "Create New Deal" flow
    (Sales & Trade-Ins -> step 4, "Trade-In Configuration").

    customer_id is a loose reference (IntegerField, not a ForeignKey) to
    Person 1's future Customer model (API spec section 7) -- see the
    integration note in common/permissions.py for why cross-app FKs to
    not-yet-built apps are avoided. Convert to a real FK once that app lands.
    """

    CONDITION_CHOICES = [
        ("EXCELLENT", "Excellent"),
        ("GOOD", "Good"),
        ("FAIR", "Fair"),
        ("POOR", "Poor"),
    ]

    customer_id = models.IntegerField(db_index=True)

    vin = models.CharField(max_length=17, blank=True)
    make = models.CharField(max_length=60, blank=True)
    model = models.CharField(max_length=60, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    mileage = models.PositiveIntegerField(null=True, blank=True)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, blank=True)
    condition_notes = models.TextField(blank=True)

    appraised_value = models.DecimalField(max_digits=12, decimal_places=2)
    appraised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="trade_in_appraisals",
    )

    # Loose reference for now (plain IntegerField): SalesInvoice doesn't
    # exist yet in this branch. Upgraded to a real ForeignKey in the
    # aya/sales-invoices branch once that model lands (1:M -- Sales
    # Invoice -> Trade-In: one invoice may have several trade-ins credited
    # to it).
    credited_invoice_id = models.IntegerField(null=True, blank=True, db_index=True)
    credited_reference = models.CharField(max_length=30, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"TradeIn #{self.pk} ({self.year} {self.make} {self.model})"

    @property
    def is_credited(self):
        return self.credited_invoice_id is not None

    def __repr__(self):
        return self.__str__()


class TaxRule(models.Model):
    """
    Admin-configured tax rates used server-side to compute
    sales_invoice.tax_amount (e.g. the 6.25% state tax shown on the
    Invoice screen). Standalone table — no FKs in or out.
    """

    APPLIES_TO_CHOICES = [
        ("VEHICLE_TYPE", "Vehicle Type"),
        ("TRANSACTION_TYPE", "Transaction Type"),
    ]

    jurisdiction = models.CharField(max_length=60)
    rate = models.DecimalField(max_digits=5, decimal_places=4, help_text="e.g. 0.0625 for 6.25%")
    applies_to = models.CharField(max_length=60, choices=APPLIES_TO_CHOICES, default="TRANSACTION_TYPE")
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["jurisdiction"]

    def __str__(self):
        return f"{self.jurisdiction} — {self.rate}"
