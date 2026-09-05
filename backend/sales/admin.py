from django.contrib import admin

from .models import Discount, SalesInvoice, TaxRule, TradeIn


@admin.register(TradeIn)
class TradeInAdmin(admin.ModelAdmin):
    list_display = ["id", "customer_id", "vin", "appraised_value", "is_credited", "created_at"]
    list_filter = ["condition"]
    search_fields = ["vin", "make", "model"]


@admin.register(TaxRule)
class TaxRuleAdmin(admin.ModelAdmin):
    list_display = ["id", "jurisdiction", "rate", "applies_to", "is_active"]
    list_filter = ["is_active", "applies_to"]


class DiscountInline(admin.TabularInline):
    model = Discount
    extra = 0


@admin.register(SalesInvoice)
class SalesInvoiceAdmin(admin.ModelAdmin):
    list_display = ["id", "invoice_number", "customer_id", "vehicle_id", "status", "total_amount", "balance_due"]
    list_filter = ["status"]
    search_fields = ["invoice_number"]
    inlines = [DiscountInline]
