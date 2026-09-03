from .api_client import APIError, request_json


ACCESS_TOKEN_SESSION_KEY = "adms_access_token"
REFRESH_TOKEN_SESSION_KEY = "adms_refresh_token"
USER_SESSION_KEY = "adms_user"


class AuthenticationRequired(Exception):
    pass


def _unwrap(payload):
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload if isinstance(payload, dict) else {}


def _token(payload, *names):
    data = _unwrap(payload)
    for name in names:
        if data.get(name):
            return data[name]
    return ""


def login(email, password):
    return request_json(
        "POST",
        "/auth/login",
        payload={"email": email, "password": password},
    )


def refresh(refresh_token):
    return request_json(
        "POST",
        "/auth/refresh",
        payload={"refresh_token": refresh_token},
    )


def current_user(access_token):
    return request_json("GET", "/auth/me", access_token=access_token)


def store_login(request, payload, *, remember=False):
    data = _unwrap(payload)
    access_token = _token(data, "access_token", "access")
    refresh_token = _token(data, "refresh_token", "refresh")
    user = data.get("user") if isinstance(data.get("user"), dict) else {}

    if not access_token:
        raise APIError("The backend response did not include an access token.")

    request.session.cycle_key()
    request.session[ACCESS_TOKEN_SESSION_KEY] = access_token
    if refresh_token:
        request.session[REFRESH_TOKEN_SESSION_KEY] = refresh_token
    request.session[USER_SESSION_KEY] = user
    request.session.set_expiry(60 * 60 * 24 * 30 if remember else 0)
    request.session.modified = True


def clear_login(request):
    for key in (
        ACCESS_TOKEN_SESSION_KEY,
        REFRESH_TOKEN_SESSION_KEY,
        USER_SESSION_KEY,
    ):
        request.session.pop(key, None)
    request.session.modified = True


def verified_user(request):
    access_token = request.session.get(ACCESS_TOKEN_SESSION_KEY, "")
    if not access_token:
        raise AuthenticationRequired

    try:
        payload = current_user(access_token)
    except APIError as error:
        refresh_token = request.session.get(REFRESH_TOKEN_SESSION_KEY, "")
        if error.status_code != 401 or not refresh_token:
            raise

        refreshed = refresh(refresh_token)
        new_access_token = _token(refreshed, "access_token", "access")
        if not new_access_token:
            raise AuthenticationRequired from error

        request.session[ACCESS_TOKEN_SESSION_KEY] = new_access_token
        new_refresh_token = _token(refreshed, "refresh_token", "refresh")
        if new_refresh_token:
            request.session[REFRESH_TOKEN_SESSION_KEY] = new_refresh_token
        request.session.modified = True
        payload = current_user(new_access_token)

    data = _unwrap(payload)
    user = data.get("user") if isinstance(data.get("user"), dict) else data
    if not isinstance(user, dict) or not user:
        raise APIError("The backend response did not include the current user.")

    request.session[USER_SESSION_KEY] = user
    request.session.modified = True
    return user


def access_token(request):
    return request.session.get(ACCESS_TOKEN_SESSION_KEY, "")
