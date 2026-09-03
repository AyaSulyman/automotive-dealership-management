"""
Wraps DRF's default exception handling so every error response follows the
API spec's standard shape:

    { "error": { "code": "...", "message": "...", "fields": {...} } }

`fields` carries per-field validation errors (from serializer.errors) when
present, otherwise it's an empty object.
"""
from rest_framework.views import exception_handler as drf_exception_handler


def standard_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    fields = {}
    message = "An error occurred."

    if isinstance(detail, dict):
        # serializer.errors style: {"field": ["msg", ...], ...}
        non_field = detail.get("detail") or detail.get("non_field_errors")
        if non_field:
            message = non_field if isinstance(non_field, str) else str(non_field[0])
        remaining = {k: v for k, v in detail.items() if k not in ("detail", "non_field_errors")}
        if remaining:
            fields = remaining
            if message == "An error occurred." and fields:
                message = "Validation failed."
    elif isinstance(detail, list) and detail:
        message = str(detail[0])
    else:
        message = str(detail)

    response.data = {
        "error": {
            "code": _code_for_status(response.status_code),
            "message": message,
            "fields": fields,
        }
    }
    return response


def _code_for_status(status_code):
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        429: "too_many_requests",
        500: "server_error",
    }.get(status_code, "error")
