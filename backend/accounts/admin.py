from django.contrib import admin

from .models import Branch, Role, UserProfile


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "created_at")
    search_fields = ("name",)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "is_active")
    search_fields = ("name",)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "branch", "phone")
    list_select_related = ("user", "role", "branch")
    search_fields = ("user__username", "user__email", "phone")
    autocomplete_fields = ("user",)