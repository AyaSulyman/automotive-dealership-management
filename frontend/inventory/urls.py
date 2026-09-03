from django.urls import path

from . import views


app_name = "inventory"

urlpatterns = [
    path("inventory/", views.inventory_page, name="inventory"),
    path("inventory/vehicles/add/", views.vehicle_add_page, name="vehicle-add"),
    path(
        "inventory/vehicles/<str:vehicle_id>/",
        views.vehicle_detail_page,
        name="vehicle-detail",
    ),
    path(
        "inventory/vehicles/<str:vehicle_id>/edit/",
        views.vehicle_edit_page,
        name="vehicle-edit",
    ),
    path(
        "inventory/vehicles/<str:vehicle_id>/remove/",
        views.vehicle_remove_page,
        name="vehicle-remove",
    ),
    path("inventory/vendors/add/", views.vendor_add_page, name="vendor-add"),
    path(
        "inventory/vendors/<str:vendor_id>/",
        views.vendor_detail_page,
        name="vendor-detail",
    ),
    path(
        "inventory/vendors/<str:vendor_id>/edit/",
        views.vendor_edit_page,
        name="vendor-edit",
    ),
    path(
        "inventory/purchase-orders/<str:purchase_order_id>/",
        views.purchase_order_detail_page,
        name="purchase-order-detail",
    ),
    path(
        "inventory/purchase-orders/<str:purchase_order_id>/status/",
        views.purchase_order_status_page,
        name="purchase-order-status",
    ),
]
