"""
Authentication endpoints (API spec section 1).

    POST /auth/login    -> { access_token, refresh_token, user }
    POST /auth/refresh  -> { access_token, refresh_token } (rotated)
    POST /auth/logout   -> blacklists the refresh token, 200
    GET  /auth/me       -> current user with role + branch
"""
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Q
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.exceptions import AuthenticationFailed, NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from common.permissions import IsAdmin

from .models import Role
from .serializers import (
    LoginRequestSerializer, LoginResponseSerializer, LogoutRequestSerializer,
    RefreshRequestSerializer, RoleSerializer, TokenPairSerializer,
    UserCreateSerializer, UserDetailSerializer, UserUpdateSerializer,
)


def _user_for_refresh(refresh):
    """Return the User a refresh token belongs to (raises on invalid/blacklisted)."""
    refresh.check_blacklist()
    try:
        return User.objects.get(pk=refresh["user_id"])
    except User.DoesNotExist:
        raise NotFound(detail="User no longer exists.")


@extend_schema_view(
    post=extend_schema(
        tags=["Authentication"],
        summary="Login with email + password",
        request=LoginRequestSerializer,
        responses={200: LoginResponseSerializer},
    ),
)
class LoginView(APIView):
    """POST /auth/login — issue an access/refresh pair + the user object."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        login = serializer.validated_data["email"].strip().lower()
        password = serializer.validated_data["password"]

        user = authenticate(request, username=login, password=password)
        if user is None:
            # Also accept a real email address, not just the username.
            match = User.objects.filter(email__iexact=login).first()
            if match is not None:
                user = authenticate(request, username=match.username, password=password)

        if user is None or not user.is_active:
            raise AuthenticationFailed(detail="Invalid email or password.")

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "user": UserDetailSerializer(user).data,
            }
        )


@extend_schema_view(
    post=extend_schema(
        tags=["Authentication"],
        summary="Refresh access token",
        request=RefreshRequestSerializer,
        responses={200: TokenPairSerializer},
    ),
)
class RefreshView(APIView):
    """POST /auth/refresh — validate + rotate the token pair."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RefreshRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw = serializer.validated_data["refresh_token"]
        try:
            refresh = RefreshToken(raw)
            user = _user_for_refresh(refresh)
        except TokenError as exc:
            raise AuthenticationFailed(detail="Invalid or expired refresh token.") from exc

        # Rotate: revoke the old refresh token, hand out a brand new pair.
        try:
            refresh.blacklist()
        except AttributeError:  # pragma: no cover - token_blacklist not installed
            pass

        new_refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access_token": str(new_refresh.access_token),
                "refresh_token": str(new_refresh),
            }
        )


@extend_schema_view(
    post=extend_schema(
        tags=["Authentication"],
        summary="Logout (invalidates the refresh token)",
        request=LogoutRequestSerializer,
        responses={200: None},
    ),
)
class LogoutView(APIView):
    """POST /auth/logout — blacklist the refresh token so it can't be reused."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw = serializer.validated_data["refresh_token"]
        try:
            refresh = RefreshToken(raw)
            refresh.blacklist()
        except TokenError:
            pass  # already invalid/blacklisted — treat logout as idempotent
        except AttributeError:  # pragma: no cover - token_blacklist not installed
            pass
        return Response({"message": "Logged out successfully."})


@extend_schema_view(
    get=extend_schema(
        tags=["Authentication"],
        summary="Authenticated user profile",
        responses={200: UserDetailSerializer},
    ),
)
class MeView(APIView):
    """GET /auth/me — the caller's own profile (drives the app header)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserDetailSerializer(request.user).data)
@extend_schema_view(get=extend_schema(tags=["Users & Roles"], summary="List role options"))
class RoleListView(generics.ListAPIView):
    """GET /roles — the three selectable roles (admin / agent / accountant)."""

    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAdmin]


@extend_schema_view(
    get=extend_schema(tags=["Users & Roles"], summary="List users (search + role/branch filters)"),
    post=extend_schema(tags=["Users & Roles"], summary="Create a user", request=UserCreateSerializer,
                       responses={201: UserDetailSerializer}),
)
class UserListCreateView(generics.ListCreateAPIView):
    """GET /users ...  POST /users — admin-only user management.

Query params: ?search=, ?role_id=, ?branch_id=, + standard pagination.
    """

    serializer_class = UserDetailSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        qs = User.objects.select_related("profile").prefetch_related("groups").order_by("id")
        params = self.request.query_params
        search = params.get("search")
        if search:
            qs = qs.filter(
                Q(username__icontains=search) | Q(email__icontains=search)
                | Q(first_name__icontains=search) | Q(last_name__icontains=search)
            )
        role_id = params.get("role_id")
        if role_id:
            qs = qs.filter(profile__role_id=role_id)
        branch_id = params.get("branch_id")
        if branch_id:
            qs = qs.filter(profile__branch_id=branch_id)
        return qs

    def get_serializer_class(self):
        if self.request.method == "POST":
            return UserCreateSerializer
        return UserDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserDetailSerializer(user).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(tags=["Users & Roles"], summary="User detail"),
    patch=extend_schema(tags=["Users & Roles"], summary="Edit a user", request=UserUpdateSerializer,
                        responses={200: UserDetailSerializer}),
    delete=extend_schema(tags=["Users & Roles"], summary="Deactivate a user (soft delete)"),
)
class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET /users/{id}  PATCH /users/{id}  DELETE /users/{id} (soft)."""

    queryset = User.objects.all()
    permission_classes = [IsAdmin]

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return UserUpdateSerializer
        return UserDetailSerializer

    def update(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = UserUpdateSerializer(user, data=request.data, partial=True,
                                          context={"user": user})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserDetailSerializer(user).data)

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response(
            {"message": f"User '{user.username}' deactivated."}, status=status.HTTP_200_OK,
        )
