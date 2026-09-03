from django.urls import path

from . import views

urlpatterns = [
    path("trade-ins", views.TradeInListCreateView.as_view(), name="trade-in-list-create"),
    path("trade-ins/<int:pk>", views.TradeInDetailView.as_view(), name="trade-in-detail"),
    path("trade-ins/<int:pk>/apply-credit", views.TradeInApplyCreditView.as_view(), name="trade-in-apply-credit"),

    path("tax-rules", views.TaxRuleListCreateView.as_view(), name="tax-rule-list-create"),
    path("tax-rules/<int:pk>", views.TaxRuleDetailView.as_view(), name="tax-rule-detail"),

    path("sales-invoices", views.SalesInvoiceListCreateView.as_view(), name="sales-invoice-list-create"),
    path("sales-invoices/<int:pk>", views.SalesInvoiceDetailView.as_view(), name="sales-invoice-detail"),
    path("sales-invoices/<int:pk>/save-draft", views.SalesInvoiceSaveDraftView.as_view(), name="sales-invoice-save-draft"),
    path("sales-invoices/<int:pk>/finalize", views.SalesInvoiceFinalizeView.as_view(), name="sales-invoice-finalize"),
    path("sales-invoices/<int:pk>/discounts", views.SalesInvoiceDiscountsView.as_view(), name="sales-invoice-discounts"),
    path("sales-invoices/<int:pk>/pdf", views.SalesInvoicePdfView.as_view(), name="sales-invoice-pdf"),
    path("sales-invoices/<int:pk>/cancel", views.SalesInvoiceCancelView.as_view(), name="sales-invoice-cancel"),
]
