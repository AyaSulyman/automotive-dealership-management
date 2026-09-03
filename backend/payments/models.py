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
    financing_account_id = models.IntegerField(null=True, blank=True, db_index=True)

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
