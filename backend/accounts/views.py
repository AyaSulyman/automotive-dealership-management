"""
Authentication endpoints (API spec section 1).

    POST /auth/login    -> { access_token, refresh_token, user }
    POST /auth/refresh  -> { access_token, refresh_token } (rotated)
    POST /auth/logout   -> blacklists the refresh token, 200
    GET  /auth/me       -> current user with role + branch
"""
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    LoginRequestSerializer, LoginResponseSerializer, LogoutRequestSerializer,
    RefreshRequestSerializer, TokenPairSerializer, UserDetailSerializer,
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