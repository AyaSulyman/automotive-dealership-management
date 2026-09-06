from django.urls import path

from . import views

urlpatterns = [
    path("vendors", views.VendorListCreateView.as_view(), name="vendor-list-create"),
    path("vendors/<int:pk>", views.VendorDetailView.as_view(), name="vendor-detail"),
    path("purchase-orders", views.PurchaseOrderListCreateView.as_view(), name="po-list-create"),
    path("purchase-orders/<int:pk>", views.PurchaseOrderDetailView.as_view(), name="po-detail"),
    path("vehicles", views.VehicleListCreateView.as_view(), name="vehicle-list-create"),
    path("vehicles/<int:pk>", views.VehicleDetailView.as_view(), name="vehicle-detail"),
    path("vehicles/<int:pk>/media", views.VehicleMediaCreateView.as_view(), name="vehicle-media-create"),
    path("vehicles/<int:pk>/media/<int:media_id>", views.VehicleMediaDeleteView.as_view(), name="vehicle-media-delete"),
    path("vehicles/<int:pk>/valuation", views.VehicleValuationCreateView.as_view(), name="vehicle-valuation-create"),
    path("documents", views.DocumentListCreateView.as_view(), name="document-list-create"),
    path("documents/<int:pk>", views.DocumentDeleteView.as_view(), name="document-delete"),
    path("documents/<int:pk>/download", views.DocumentDownloadView.as_view(), name="document-download"),
]
