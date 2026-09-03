from django.contrib import admin

from .models import TradeIn


@admin.register(TradeIn)
class TradeInAdmin(admin.ModelAdmin):
    list_display = ["id", "customer_id", "vin", "appraised_value", "is_credited", "created_at"]
    list_filter = ["condition"]
    search_fields = ["vin", "make", "model"]
