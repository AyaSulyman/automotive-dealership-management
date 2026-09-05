from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "user", "action", "entity_type", "entity_id"]
    list_filter = ["action", "entity_type"]
    search_fields = ["entity_type"]
    readonly_fields = ["user", "action", "entity_type", "entity_id", "changes", "created_at"]
