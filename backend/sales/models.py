from django.conf import settings
from django.db import models


class SalesInvoice(models.Model):
    """
    The deal / invoice lifecycle (Sales & Trade-Ins "Create New Deal" flow,
    Invoice screen). customer_id / vehicle_id / branch_id are loose
    references to Person 1's Customer / Vehicle / Branch models (API spec
    sections 5, 6, 7) — see common/permissions.py for why cross-app FKs to
    not-yet-built apps are avoided.
    """

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("OPEN", "Open"),
        ("PAID", "Paid"),
        ("CANCELLED", "Cancelled"),
    ]

    invoice_number = models.CharField(max_length=30, unique=True, null=True, blank=True)

    customer_id = models.IntegerField(db_index=True)
    vehicle_id = models.IntegerField(db_index=True)
    branch_id = models.IntegerField(null=True, blank=True, db_index=True)
    salesperson = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales_invoices",
    )

    sale_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")

    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    trade_in_credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.invoice_number or f"DRAFT-{self.pk}"

    def recompute_totals(self, tax_rate=None):
        """Subtotal -> tax -> total -> balance_due, in that order.
        Called only while a deal is still DRAFT (selling_price/discount/tax/
        trade-in are all still editable then), so balance_due is simply
        reset to total_amount every time. Once a deal is finalized (OPEN),
        the payments app decrements balance_due directly as payments land
        instead of calling this method."""
        self.subtotal = self.selling_price - self.discount_amount
        if tax_rate is not None:
            self.tax_amount = (self.subtotal * tax_rate).quantize(self.selling_price)
        self.total_amount = self.subtotal + self.tax_amount - self.trade_in_credit
        self.balance_due = self.total_amount


class Discount(models.Model):
    """Line-item discount on a SalesInvoice. `approved_by` exists for a
    future manager-approval workflow — not enforced in this MVP (see the
    API spec's note on §9 discounts)."""

    DISCOUNT_TYPE_CHOICES = [
        ("FIXED", "Fixed Amount"),
        ("PERCENTAGE", "Percentage"),
    ]

    invoice = models.ForeignKey(SalesInvoice, on_delete=models.CASCADE, related_name="discounts")
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="approved_discounts",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Discount({self.discount_type}, {self.amount}) on invoice {self.invoice_id}"


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

    # Real FK now that SalesInvoice exists in this app (was a loose
    # IntegerField in the aya/trade-ins branch). Nullable, no uniqueness
    # constraint: one invoice may have several trade-ins credited to it
    # (1:M -- Sales Invoice -> Trade-In).
    credited_invoice = models.ForeignKey(
        "sales.SalesInvoice", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="trade_ins",
    )
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
