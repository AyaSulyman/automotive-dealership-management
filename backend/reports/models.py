from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """
    Internal audit trail (SEC-03, MVP requirement). Not surfaced in any of
    the 10 UI screens, but exposed here for admin troubleshooting. Rows are
    written explicitly from the sales/payments views at the moments that
    matter (finalize, cancel, record payment, add discount, credit a
    trade-in, create a financing account) via reports/audit.py's
    log_action() helper -- not via blind model signals, so the log
    captures *who* performed the action, not just that a row changed.
    """

    ACTION_CHOICES = [
        ("CREATE", "Create"),
        ("UPDATE", "Update"),
        ("DELETE", "Delete"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_entries")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    entity_type = models.CharField(max_length=50, db_index=True)
    entity_id = models.IntegerField(db_index=True)
    changes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} {self.entity_type}#{self.entity_id} by {self.user_id}"
