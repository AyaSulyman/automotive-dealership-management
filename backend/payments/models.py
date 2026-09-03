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
