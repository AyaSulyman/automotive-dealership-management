from django.urls import path

from . import views

urlpatterns = [
    path("vendors", views.VendorListCreateView.as_view(), name="vendor-list-create"),
    path("vendors/<int:pk>", views.VendorDetailView.as_view(), name="vendor-detail"),
    path("purchase-orders", views.PurchaseOrderListCreateView.as_view(), name="po-list-create"),
    path("purchase-orders/<int:pk>", views.PurchaseOrderDetailView.as_view(), name="po-detail"),
]