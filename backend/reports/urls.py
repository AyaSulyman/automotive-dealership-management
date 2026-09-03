from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/overview", views.DashboardOverviewView.as_view(), name="dashboard-overview"),
    path("dashboard/recent-invoices", views.RecentInvoicesView.as_view(), name="dashboard-recent-invoices"),
    path("dashboard/recent-payments", views.RecentPaymentsView.as_view(), name="dashboard-recent-payments"),
]
