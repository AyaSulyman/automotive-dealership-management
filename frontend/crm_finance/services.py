from services.api_client import request_json


def get_customers(access_token, *, search="", page=1, page_size=10):
    return request_json(
        "GET",
        "/customers",
        access_token=access_token,
        params={"search": search, "page": page, "page_size": page_size},
    )


def get_customer(access_token, customer_id):
    return request_json(
        "GET", f"/customers/{customer_id}", access_token=access_token
    )


def get_customer_history(access_token, customer_id):
    return request_json(
        "GET",
        f"/customers/{customer_id}/history",
        access_token=access_token,
    )


def create_customer(access_token, customer):
    return request_json(
        "POST", "/customers", access_token=access_token, payload=customer
    )


def update_customer(access_token, customer_id, customer):
    return request_json(
        "PATCH",
        f"/customers/{customer_id}",
        access_token=access_token,
        payload=customer,
    )


def get_sales_invoices(access_token, *, status="", page_size=100):
    return request_json(
        "GET",
        "/sales-invoices",
        access_token=access_token,
        params={"status": status, "page_size": page_size},
    )


def get_payments(
    access_token,
    *,
    invoice_id="",
    method="",
    date_from="",
    date_to="",
    page_size=100,
):
    return request_json(
        "GET",
        "/payments",
        access_token=access_token,
        params={
            "invoice_id": invoice_id,
            "method": method,
            "date_from": date_from,
            "date_to": date_to,
            "page_size": page_size,
        },
    )


def get_payment(access_token, payment_id):
    return request_json(
        "GET", f"/payments/{payment_id}", access_token=access_token
    )


def create_payment(access_token, payment):
    return request_json(
        "POST", "/payments", access_token=access_token, payload=payment
    )


def get_payment_schedules(access_token, *, invoice_id="", page_size=100):
    return request_json(
        "GET",
        "/payment-schedules",
        access_token=access_token,
        params={"invoice_id": invoice_id, "page_size": page_size},
    )


def get_financing_accounts(access_token, *, invoice_id="", page_size=100):
    return request_json(
        "GET",
        "/financing-accounts",
        access_token=access_token,
        params={"invoice_id": invoice_id, "page_size": page_size},
    )


def get_finance_overview(access_token):
    return request_json(
        "GET", "/reports/finance/overview", access_token=access_token
    )


def get_vehicle_financial_summary(access_token, *, vehicle_id):
    return request_json(
        "GET",
        "/reports/vehicle-financial-summary",
        access_token=access_token,
        params={"vehicle_id": vehicle_id},
    )

