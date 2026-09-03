from django.conf import settings
from django.db import models


class Payment(models.Model):
    """
    Payments Ledger / "Record Payment" (Payments & Financing screen,
    Payment Entry & Receipt screen).

    financing_account_id is a loose reference for now (plain IntegerField)
    -- upgraded to a real FK in the aya/financing-accounts branch once that
    model exists, same pattern used for TradeIn.credited_invoice in the
    sales app.
    """

    METHOD_CHOICES = [
        ("CASH", "Cash"),
        ("CARD", "Card"),
        ("TRANSFER", "Bank Transfer"),
        ("CHECK", "Check"),
        ("ACH", "ACH"),
    ]

    invoice = models.ForeignKey("sales.SalesInvoice", on_delete=models.PROTECT, related_name="payments")
    financing_account = models.ForeignKey(
        "payments.FinancingAccount", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="payments",
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    reference_number = models.CharField(max_length=60, blank=True)
    receipt_number = models.CharField(max_length=30, unique=True)
    notes = models.TextField(blank=True)

    paid_at = models.DateTimeField()
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recorded_payments",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_at"]

    def __str__(self):
        return f"{self.receipt_number} — {self.amount}"


class PaymentSchedule(models.Model):
    """
    One row per scheduled installment (Payments & Financing -> Payment
    Schedules tab). Intentionally 1:M against SalesInvoice -- a financed
    deal has multiple rows, one per due date, not one aggregate "schedule"
    object (see the ERD notes on this exact point).
    """

    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("PAID", "Paid"),
        ("OVERDUE", "Overdue"),
    ]

    invoice = models.ForeignKey("sales.SalesInvoice", on_delete=models.CASCADE, related_name="payment_schedule")
    installment_number = models.PositiveIntegerField()
    due_date = models.DateField()
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")

    class Meta:
        ordering = ["invoice_id", "installment_number"]
        constraints = [
            models.UniqueConstraint(fields=["invoice", "installment_number"], name="unique_installment_per_invoice"),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_id} — installment {self.installment_number}"

    @property
    def remaining(self):
        return self.amount_due - self.amount_paid


class FinancingAccount(models.Model):
    """
    Payments & Financing -> Financing Agreements tab. Genuine 1:1 with
    SalesInvoice -- a deal has at most one financing account -- enforced
    with OneToOneField (UNIQUE constraint under the hood). No amortization
    engine yet, just the basic capture fields from the API spec.
    """

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("PAID_OFF", "Paid Off"),
        ("DEFAULT", "Default"),
    ]

    invoice = models.OneToOneField("sales.SalesInvoice", on_delete=models.CASCADE, related_name="financing_account")
    lender_name = models.CharField(max_length=120, blank=True)
    down_payment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    term_months = models.PositiveIntegerField()
    interest_rate = models.DecimalField(max_digits=5, decimal_places=4, help_text="e.g. 0.0599 for 5.99%")
    monthly_payment = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Financing for invoice {self.invoice_id} ({self.lender_name})"


class Statement(models.Model):
    """
    Customer statement (Customers screen -> "Generate Statement"). customer_id
    is a loose reference to Person 1's future Customer model (same pattern
    as elsewhere). `summary` is a computed JSON snapshot taken at generation
    time (invoices/payments within the period + resulting balance) so a
    previously-issued statement never silently changes if later payments
    land -- it's a point-in-time record, not a live query.
    """

    customer_id = models.IntegerField(db_index=True)
    period_start = models.DateField()
    period_end = models.DateField()
    summary = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return f"Statement for customer {self.customer_id} ({self.period_start} to {self.period_end})"
