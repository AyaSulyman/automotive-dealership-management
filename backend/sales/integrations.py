"""
Integration hooks into the inventory domain (API spec sections 5-7).
"""
import logging

logger = logging.getLogger(__name__)


def mark_vehicle_sold(vehicle_id):
    """Called from SalesInvoice.finalize(). Flips the inventory Vehicle to
    SOLD once Person 1's inventory app is available."""
    try:
        from inventory.models import Vehicle

        Vehicle.objects.filter(pk=vehicle_id).update(status="SOLD")
    except Exception:
        logger.warning("inventory.Vehicle not available; vehicle %s not marked SOLD", vehicle_id)


def mark_vehicle_available(vehicle_id):
    """Called if a finalized deal is ever reversed (Future — SAL-04)."""
    try:
        from inventory.models import Vehicle

        Vehicle.objects.filter(pk=vehicle_id).update(status="AVAILABLE")
    except Exception:
        logger.warning("inventory.Vehicle not available; vehicle %s not marked AVAILABLE", vehicle_id)
