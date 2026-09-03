from django.contrib import admin

from .models import Payment, PaymentSchedule


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["id", "receipt_number", "invoice", "amount", "method", "paid_at"]
    list_filter = ["method"]
    search_fields = ["receipt_number", "reference_number"]


@admin.register(PaymentSchedule)
class PaymentScheduleAdmin(admin.ModelAdmin):
    list_display = ["id", "invoice", "installment_number", "due_date", "amount_due", "amount_paid", "status"]
    list_filter = ["status"]
