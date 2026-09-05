from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/overview", views.DashboardOverviewView.as_view(), name="dashboard-overview"),
    path("dashboard/recent-invoices", views.RecentInvoicesView.as_view(), name="dashboard-recent-invoices"),
    path("dashboard/recent-payments", views.RecentPaymentsView.as_view(), name="dashboard-recent-payments"),

    path("reports/finance/overview", views.FinanceOverviewView.as_view(), name="finance-overview"),
    path("reports/vehicle-financial-summary", views.VehicleFinancialSummaryView.as_view(), name="vehicle-financial-summary"),

    path("audit-log", views.AuditLogListView.as_view(), name="audit-log-list"),
]
