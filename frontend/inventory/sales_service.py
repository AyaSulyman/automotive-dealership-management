from services.api_client import request_json, get_all, request_binary


def options(token, invoice_id=None):
    return (
        get_all("/sales/customer-options", access_token=token),
        get_all("/sales/vehicle-options", access_token=token, params={"invoice_id": invoice_id or ""}),
    )


def invoices(token, **params):
    return request_json("GET", "/sales-invoices", access_token=token, params=params)


def invoice(token, invoice_id):
    return request_json("GET", f"/sales-invoices/{invoice_id}", access_token=token)


def worksheet(token, payload):
    return request_json("POST", "/sales/deal-worksheet", access_token=token, payload=payload)


def invoice_pdf(token, invoice_id):
    return request_binary(f"/sales-invoices/{invoice_id}/pdf", access_token=token)
