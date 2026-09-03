from django.urls import path

from . import views

urlpatterns = [
    path("payments", views.PaymentListCreateView.as_view(), name="payment-list-create"),
    path("payments/<int:pk>", views.PaymentDetailView.as_view(), name="payment-detail"),
    path("payments/<int:pk>/receipt", views.PaymentReceiptView.as_view(), name="payment-receipt"),
    path("reports/payments/export", views.PaymentsExportView.as_view(), name="payments-export"),

    path("payment-schedules", views.PaymentScheduleListView.as_view(), name="payment-schedule-list"),
    path("payment-schedules/<int:pk>", views.PaymentScheduleDetailUpdateView.as_view(), name="payment-schedule-detail"),
    path("sales-invoices/<int:pk>/generate-schedule", views.GenerateScheduleView.as_view(), name="generate-schedule"),

    path("financing-accounts", views.FinancingAccountListCreateView.as_view(), name="financing-account-list-create"),
    path("financing-accounts/<int:pk>", views.FinancingAccountDetailView.as_view(), name="financing-account-detail"),
]
