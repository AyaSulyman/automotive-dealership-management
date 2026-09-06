from urllib.parse import urljoin

import requests
from django.conf import settings


class APIError(Exception):
    def __init__(self, message, *, status_code=0, field_errors=None, payload=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.field_errors = field_errors or {}
        self.payload = payload


class APIConfigurationError(APIError):
    pass


def get_api_base_url():
    return str(getattr(settings, "ADMS_API_BASE_URL", "")).strip().rstrip("/")


def api_is_configured():
    return bool(get_api_base_url())


def build_api_url(path):
    base_url = get_api_base_url()
    if not base_url:
        raise APIConfigurationError(
            "The backend API URL has not been configured yet."
        )
    return urljoin(f"{base_url}/", str(path).lstrip("/"))


def _error_details(payload, fallback):
    if not isinstance(payload, dict):
        return fallback, {}

    standard_error = payload.get("error")
    if isinstance(standard_error, dict):
        return (
            standard_error.get("message") or fallback,
            standard_error.get("fields") or {},
        )

    detail = payload.get("detail")
    if isinstance(detail, str):
        return detail, {}
    if isinstance(detail, list) and detail:
        first = detail[0]
        if isinstance(first, dict):
            return first.get("msg") or fallback, {}

    return payload.get("message") or fallback, {key: value for key, value in payload.items() if key not in {"detail", "message"}}


def request_json(
    method,
    path,
    *,
    access_token="",
    params=None,
    payload=None,
    files=None,
):
    headers = {"Accept": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    timeout = float(getattr(settings, "ADMS_API_TIMEOUT", 10))

    try:
        response = requests.request(
            method=method,
            url=build_api_url(path),
            headers=headers,
            params=params,
            json=payload if files is None else None,
            data=payload if files is not None else None,
            files=files,
            timeout=timeout,
        )
    except requests.RequestException as error:
        raise APIError(
            "The backend service could not be reached. Please try again.",
            payload=error,
        ) from error

    if response.status_code == 204:
        response_payload = {}
    else:
        try:
            response_payload = response.json()
        except ValueError:
            response_payload = {}

    if not response.ok:
        message, field_errors = _error_details(
            response_payload,
            "The backend could not complete the request.",
        )
        raise APIError(
            message,
            status_code=response.status_code,
            field_errors=field_errors,
            payload=response_payload,
        )

    return response_payload


def get_all(path, *, access_token, params=None):
    """Collect all pages, using our configured API host (never a response-supplied URL)."""
    query = dict(params or {})
    query["page_size"] = 500
    results = []
    for page in range(1, 1001):
        query["page"] = page
        payload = request_json("GET", path, access_token=access_token, params=query)
        if isinstance(payload, list):
            return payload
        rows = payload.get("results", payload.get("data", []))
        if not isinstance(rows, list):
            raise APIError("The backend returned an invalid list.")
        results.extend(rows)
        if not payload.get("next"):
            return results
    raise APIError("Too many results. Narrow the search and try again.")


def request_binary(path, *, access_token, params=None):
    try:
        response = requests.get(
            build_api_url(path), params=params,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=float(getattr(settings, "ADMS_API_TIMEOUT", 10)),
        )
    except requests.RequestException as error:
        raise APIError("The backend service could not be reached.") from error
    if not response.ok:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        message, fields = _error_details(payload, "The file could not be downloaded.")
        raise APIError(message, status_code=response.status_code, field_errors=fields)
    return response.content
