from django.contrib import admin

from .models import Document, PurchaseOrder, Vehicle, VehicleMedia, VehicleValuation, Vendor


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_person", "email", "phone", "is_active")
    search_fields = ("name", "contact_person", "email")


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("po_number", "vendor", "order_date", "status", "created_at")
    list_filter = ("status", "order_date")
    search_fields = ("po_number", "vendor__name")


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("vin", "make", "model", "year", "status", "total_cost_basis", "branch")
    list_filter = ("status", "condition", "make")
    search_fields = ("vin", "make", "model")


@admin.register(VehicleMedia)
class VehicleMediaAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "media_type", "caption", "created_at")
    list_filter = ("media_type",)


@admin.register(VehicleValuation)
class VehicleValuationAdmin(admin.ModelAdmin):
    list_display = ("vehicle", "value", "source", "appraised_by", "created_at")
    list_filter = ("source",)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("related_type", "related_id", "doc_type", "original_filename", "created_at")
    list_filter = ("doc_type", "related_type")
    search_fields = ("original_filename",)