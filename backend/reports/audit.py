"""
Call this from sales/views.py and payments/views.py at the moments that
matter -- it's a thin wrapper so those apps don't need a hard import of
reports.models at module load time (avoids any import-order fragility).
"""


def log_action(user, action, entity_type, entity_id, changes=None):
    from .models import AuditLog

    AuditLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes or {},
    )
