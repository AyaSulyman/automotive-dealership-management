"""
Applies a recorded payment to the invoice's payment_schedule rows, oldest
due_date first, splitting across multiple installments if the payment is
larger than what's left on the next one.
"""


def apply_payment_to_schedule(invoice, amount, paid_at):
    from .models import PaymentSchedule

    remaining = amount
    rows = PaymentSchedule.objects.filter(
        invoice=invoice, status__in=["PENDING", "OVERDUE"],
    ).order_by("due_date", "installment_number")

    for row in rows:
        if remaining <= 0:
            break
        applied = min(remaining, row.remaining)
        if applied <= 0:
            continue
        row.amount_paid = row.amount_paid + applied
        row.status = "PAID" if row.amount_paid >= row.amount_due else row.status
        row.save(update_fields=["amount_paid", "status"])
        remaining -= applied
