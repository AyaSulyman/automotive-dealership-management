from django.urls import path

from . import views

urlpatterns = [
    path("trade-ins", views.TradeInListCreateView.as_view(), name="trade-in-list-create"),
    path("trade-ins/<int:pk>", views.TradeInDetailView.as_view(), name="trade-in-detail"),
    path("trade-ins/<int:pk>/apply-credit", views.TradeInApplyCreditView.as_view(), name="trade-in-apply-credit"),

    path("tax-rules", views.TaxRuleListCreateView.as_view(), name="tax-rule-list-create"),
    path("tax-rules/<int:pk>", views.TaxRuleDetailView.as_view(), name="tax-rule-detail"),
]
