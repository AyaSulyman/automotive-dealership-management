"""
Called from Payment creation to update the matching payment_schedule row's
amount_paid/status. PaymentSchedule doesn't exist yet in this branch --
this is a no-op stub, replaced with the real lookup in
aya/payment-schedules without changing the call site in views.py.
"""
import logging

logger = logging.getLogger(__name__)


def apply_payment_to_schedule(invoice, amount, paid_at):
    logger.info(
        "TODO(integration): apply payment of %s (paid_at=%s) to the next "
        "open payment_schedule row for invoice %s", amount, paid_at, invoice.pk,
    )
