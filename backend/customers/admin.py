from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "phone", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("first_name", "last_name", "email", "phone")