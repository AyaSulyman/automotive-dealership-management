from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["id", "receipt_number", "invoice", "amount", "method", "paid_at"]
    list_filter = ["method"]
    search_fields = ["receipt_number", "reference_number"]
