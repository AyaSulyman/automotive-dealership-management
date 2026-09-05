from django.contrib import admin
from django.urls import include, path

from .views import (
    dashboard_page,
    employee_add_page,
    employee_edit_page,
    login_page,
)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", login_page, name="login"),
    path("login/", login_page, name="login-page"),
    path("dashboard/", dashboard_page, name="dashboard"),
    path(
        "dashboard/employees/add/",
        employee_add_page,
        name="employee-add",
    ),
    path(
        "dashboard/employees/<int:employee_id>/edit/",
        employee_edit_page,
        name="employee-edit",
    ),
    path("", include("inventory.urls")),
    path("", include("crm_finance.urls")),
]
