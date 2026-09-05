from django.contrib import admin

from .models import PurchaseOrder, Vendor


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_person", "email", "phone", "is_active")
    search_fields = ("name", "contact_person", "email")


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("po_number", "vendor", "order_date", "status", "created_at")
    list_filter = ("status", "order_date")
    search_fields = ("po_number", "vendor__name")