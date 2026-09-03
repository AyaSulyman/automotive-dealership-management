from django.contrib import admin

from .models import TaxRule, TradeIn


@admin.register(TradeIn)
class TradeInAdmin(admin.ModelAdmin):
    list_display = ["id", "customer_id", "vin", "appraised_value", "is_credited", "created_at"]
    list_filter = ["condition"]
    search_fields = ["vin", "make", "model"]


@admin.register(TaxRule)
class TaxRuleAdmin(admin.ModelAdmin):
    list_display = ["id", "jurisdiction", "rate", "applies_to", "is_active"]
    list_filter = ["is_active", "applies_to"]
