from django.urls import path

from . import views

urlpatterns = [
    path("customers", views.CustomerListCreateView.as_view(), name="customer-list-create"),
    path("customers/<int:pk>", views.CustomerDetailView.as_view(), name="customer-detail"),
    path("customers/<int:pk>/history", views.CustomerHistoryView.as_view(), name="customer-history"),
    path("customers/<int:pk>/balance", views.CustomerBalanceView.as_view(), name="customer-balance"),
    path("customers/<int:pk>/statement", views.CustomerStatementView.as_view(), name="customer-statement"),
]