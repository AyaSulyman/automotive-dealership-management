from django.urls import path

from . import views, sales_views


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
    path("inventory/vehicles/<str:vehicle_id>/documents/", views.vehicle_documents_page, name="vehicle-documents"),
    path("inventory/vehicles/<str:vehicle_id>/documents/<int:document_id>/download/", views.vehicle_document_download, name="vehicle-document-download"),
    path("inventory/vehicles/<str:vehicle_id>/documents/<int:document_id>/delete/", views.vehicle_document_delete, name="vehicle-document-delete"),
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

    path("inventory/deals/", sales_views.deal_list_page, name="deal-list"),
    path("inventory/deals/<int:deal_id>/pdf/", sales_views.deal_invoice_pdf, name="deal-pdf"),
    path("inventory/deals/add/", sales_views.deal_add_page, name="deal-add"),
    path("inventory/deals/<str:deal_id>/", sales_views.deal_detail_page, name="deal-detail"),
    path("inventory/deals/<str:deal_id>/edit/", sales_views.deal_edit_page, name="deal-edit"),
    path('deals/<int:deal_id>/invoice/', sales_views.deal_invoice_view, name='deal-invoice-legacy'),
    path('inventory/deals/<int:deal_id>/invoice/', sales_views.deal_invoice_view, name='deal-invoice'),
]
