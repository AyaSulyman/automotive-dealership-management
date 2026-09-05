"""
Integration hooks into Person 1's inventory domain (API spec sections 5-7:
Vehicles, Customers). That app doesn't exist yet, so these are no-op stubs
with a clear TODO — swap the body for a real model call once it lands,
without changing any call sites in views.py.
"""
import logging

logger = logging.getLogger(__name__)


def mark_vehicle_sold(vehicle_id):
    """Called from SalesInvoice.finalize(). TODO once catalog app exists:
        from catalog.models import Vehicle
        Vehicle.objects.filter(pk=vehicle_id).update(status="SOLD")
    """
    logger.info("TODO(integration): mark vehicle %s as SOLD", vehicle_id)


def mark_vehicle_available(vehicle_id):
    """Called if a finalized deal is ever reversed (Future — SAL-04)."""
    logger.info("TODO(integration): mark vehicle %s as AVAILABLE", vehicle_id)
