from django.urls import path

from . import views


app_name = "crm_finance"

urlpatterns = [
    path("customers/", views.customers_page, name="customers"),
    path("customers/add/", views.customer_add_page, name="customer-add"),
    path(
        "customers/<str:customer_id>/",
        views.customer_detail_page,
        name="customer-detail",
    ),
    path(
        "customers/<str:customer_id>/edit/",
        views.customer_edit_page,
        name="customer-edit",
    ),
    path("payments/", views.payments_page, name="payments"),
    path("payments/export/", views.payments_export, name="payments-export"),
    path("payments/record/", views.payment_record_page, name="payment-record"),
    path(
        "payments/<str:payment_id>/receipt/",
        views.payment_receipt_page,
        name="payment-receipt",
    ),
    path(
        "payments/<str:payment_id>/receipt.pdf",
        views.payment_receipt_pdf,
        name="payment-receipt-pdf",
    ),
    path(
        "finance-reports/",
        views.finance_reports_page,
        name="finance-reports",
    ),
]
