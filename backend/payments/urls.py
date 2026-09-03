from django.urls import path

from . import views

urlpatterns = [
    path("payments", views.PaymentListCreateView.as_view(), name="payment-list-create"),
    path("payments/<int:pk>", views.PaymentDetailView.as_view(), name="payment-detail"),
    path("payments/<int:pk>/receipt", views.PaymentReceiptView.as_view(), name="payment-receipt"),
    path("reports/payments/export", views.PaymentsExportView.as_view(), name="payments-export"),
]
