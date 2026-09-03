from .api_client import request_json


def get_overview(access_token):
    return request_json(
        "GET", "/dashboard/overview", access_token=access_token
    )


def get_recent_invoices(access_token, *, limit=5):
    return request_json(
        "GET",
        "/dashboard/recent-invoices",
        access_token=access_token,
        params={"limit": limit},
    )


def get_recent_payments(access_token, *, limit=5):
    return request_json(
        "GET",
        "/dashboard/recent-payments",
        access_token=access_token,
        params={"limit": limit},
    )


def get_employees(access_token, *, search=""):
    return request_json(
        "GET",
        "/users",
        access_token=access_token,
        params={"search": search, "page_size": 25},
    )


def get_employee(access_token, employee_id):
    return request_json(
        "GET", f"/users/{employee_id}", access_token=access_token
    )


def create_employee(access_token, employee):
    return request_json(
        "POST", "/users", access_token=access_token, payload=employee
    )


def update_employee(access_token, employee_id, employee):
    return request_json(
        "PATCH",
        f"/users/{employee_id}",
        access_token=access_token,
        payload=employee,
    )
