from django.urls import path

from . import views

urlpatterns = [
    path("auth/login", views.LoginView.as_view(), name="auth-login"),
    path("auth/refresh", views.RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout", views.LogoutView.as_view(), name="auth-logout"),
    path("auth/me", views.MeView.as_view(), name="auth-me"),
    path("roles", views.RoleListView.as_view(), name="role-list"),
    path("users", views.UserListCreateView.as_view(), name="user-list-create"),
    path("users/<int:pk>", views.UserDetailView.as_view(), name="user-detail"),
]