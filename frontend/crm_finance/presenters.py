from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from services.presenters import first_value, list_results, unwrap


def decimal_value(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def currency(value):
    return "$" + f"{decimal_value(value):,.2f}"


def currency_or_dash(value):
    return "—" if value in (None, "") else currency(value)


def date_value(value):
    if isinstance(value, (date, datetime)):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return value


def customer_row(customer):
    customer_id = first_value(customer, ("id", "customer_id"), "")
    number = first_value(
        customer,
        ("customer_number", "customer_code"),
        f"CUS-{customer_id}" if customer_id else "—",
    )
    combined_name = " ".join(
        str(customer.get(part) or "").strip()
        for part in ("first_name", "last_name")
    ).strip()
    address_parts = [
        customer.get("address"),
        customer.get("city"),
        customer.get("state"),
        customer.get("zip_code"),
    ]
    status = str(customer.get("status") or "ACTIVE").upper()
    return {
        "id": customer_id,
        "number": number,
        "name": combined_name
        or first_value(customer, ("full_name", "name"), "—"),
        "id_type": str(customer.get("id_type") or "").replace("_", " ").title(),
        "id_number": customer.get("id_number") or "—",
        "phone": customer.get("phone") or "—",
        "email": customer.get("email") or "—",
        "address": ", ".join(str(part) for part in address_parts if part) or "—",
        "status": status,
        "status_display": status.replace("_", " ").title(),
        "created_at": date_value(customer.get("created_at")),
    }


def customer_rows(payload):
    return [
        customer_row(item)
        for item in list_results(payload)
        if isinstance(item, dict)
    ]


def _nested_name(value, default="—"):
    if isinstance(value, dict):
        return (
            value.get("full_name")
            or value.get("name")
            or value.get("display_name")
            or default
        )
    return value or default


def invoice_row(invoice):
    customer = invoice.get("customer")
    vehicle = invoice.get("vehicle")
    if isinstance(vehicle, dict):
        vehicle_name = " ".join(
            str(vehicle.get(field) or "").strip()
            for field in ("year", "make", "model")
        ).strip()
        vin = vehicle.get("vin") or ""
        vehicle_id = vehicle.get("id") or invoice.get("vehicle_id")
    else:
        vehicle_name = vehicle or invoice.get("vehicle_name") or "—"
        vin = invoice.get("vin") or ""
        vehicle_id = invoice.get("vehicle_id")
    balance = decimal_value(invoice.get("balance_due"))
    return {
        "id": first_value(invoice, ("id", "invoice_id"), ""),
        "number": first_value(invoice, ("invoice_number", "number"), "—"),
        "customer": invoice.get("customer_name") or _nested_name(customer),
        "customer_id": invoice.get("customer_id")
        or (customer.get("id") if isinstance(customer, dict) else None),
        "vehicle": vehicle_name,
        "vehicle_id": vehicle_id,
        "vin": vin,
        "total_value": decimal_value(invoice.get("total_amount")),
        "total_display": currency(invoice.get("total_amount")),
        "balance_value": balance,
        "balance_display": currency(balance),
        "status": str(invoice.get("status") or "OPEN").upper(),
    }


def invoice_rows(payload):
    return [
        invoice_row(item)
        for item in list_results(payload)
        if isinstance(item, dict)
    ]


def payment_row(payment):
    invoice = payment.get("invoice")
    customer = payment.get("customer")
    vehicle = payment.get("vehicle")
    if isinstance(invoice, dict):
        invoice_id = invoice.get("id")
        invoice_number = invoice.get("invoice_number") or invoice.get("number")
    else:
        invoice_id = payment.get("invoice_id") or invoice
        invoice_number = payment.get("invoice_number")
    if isinstance(vehicle, dict):
        vehicle = " ".join(
            str(vehicle.get(field) or "").strip()
            for field in ("year", "make", "model")
        ).strip()
    method = str(payment.get("method") or "OTHER").upper()
    return {
        "id": first_value(payment, ("id", "payment_id"), ""),
        "receipt": first_value(
            payment, ("receipt_number", "receipt"), "Pending"
        ),
        "invoice_id": invoice_id,
        "invoice": invoice_number or "—",
        "customer": payment.get("customer_name")
        or _nested_name(customer)
        or (
            f'Customer #{payment.get("customer_id")}'
            if payment.get("customer_id")
            else "—"
        ),
        "vehicle": vehicle or payment.get("vehicle_name") or "—",
        "amount_value": decimal_value(payment.get("amount")),
        "amount": currency(payment.get("amount")),
        "method": method.replace("_", " ").title(),
        "method_key": method.lower(),
        "reference": payment.get("reference_number") or "—",
        "paid_at": date_value(payment.get("paid_at")),
        "recorded_by": payment.get("recorded_by_name")
        or _nested_name(payment.get("recorded_by")),
        "balance_after": currency(payment.get("balance_after", 0)),
    }


def payment_rows(payload):
    return [
        payment_row(item)
        for item in list_results(payload)
        if isinstance(item, dict)
    ]


def schedule_rows(payload):
    rows = []
    for item in list_results(payload):
        if not isinstance(item, dict):
            continue
        invoice = item.get("invoice")
        rows.append(
            {
                "id": item.get("id"),
                "invoice": item.get("invoice_number")
                or (
                    invoice.get("invoice_number")
                    if isinstance(invoice, dict)
                    else None
                )
                or f'Invoice {item.get("invoice_id") or invoice or "—"}',
                "installment": item.get("installment_number") or "—",
                "due_date": date_value(item.get("due_date")),
                "amount_due": currency(item.get("amount_due")),
                "amount_paid": currency(item.get("amount_paid")),
                "status": str(item.get("status") or "PENDING").upper(),
            }
        )
    return rows


def financing_rows(payload):
    rows = []
    for item in list_results(payload):
        if not isinstance(item, dict):
            continue
        invoice = item.get("invoice")
        rate = decimal_value(
            first_value(item, ("interest_rate", "rate"), 0)
        )
        if abs(rate) <= 1:
            rate *= 100
        rows.append(
            {
                "id": item.get("id"),
                "invoice": item.get("invoice_number")
                or (
                    invoice.get("invoice_number")
                    if isinstance(invoice, dict)
                    else None
                )
                or f'Invoice {item.get("invoice_id") or invoice or "—"}',
                "lender": first_value(
                    item, ("lender_name", "lender"), "—"
                ),
                "down_payment": currency(item.get("down_payment")),
                "term": item.get("term_months") or "—",
                "rate": f"{rate:.2f}%",
                "monthly_payment": currency(item.get("monthly_payment")),
                "status": str(item.get("status") or "ACTIVE").upper(),
            }
        )
    return rows


def history_rows(payload):
    data = unwrap(payload)
    if isinstance(data, dict) and isinstance(data.get("timeline"), list):
        items = data["timeline"]
    else:
        items = list_results(payload)
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = str(first_value(item, ("type", "event_type"), "activity")).lower()
        if kind == "invoice":
            description = f'Sales invoice {str(item.get("status") or "").title()}'.strip()
        elif kind == "payment":
            description = f'Payment via {str(item.get("method") or "other").replace("_", " ").title()}'
        elif kind == "trade_in":
            description = " ".join(
                str(item.get(field) or "").strip()
                for field in ("year", "make", "model")
            ).strip() or "Trade-in appraisal"
        else:
            description = item.get("description") or "Account activity"
        rows.append(
            {
                "type": kind,
                "type_display": kind.replace("_", " ").title(),
                "reference": first_value(
                    item, ("reference", "invoice_number", "receipt_number"), "—"
                ),
                "description": description,
                "date": date_value(
                    first_value(item, ("date", "created_at", "paid_at"), None)
                ),
                "amount": currency(
                    first_value(
                        item,
                        ("amount", "total_amount", "appraised_value"),
                        0,
                    )
                ),
            }
        )
    return rows


def finance_overview(payload):
    data = unwrap(payload)
    if not isinstance(data, dict):
        data = {}
    return {
        "total_sales": currency(
            first_value(data, ("total_sales_mtd", "total_sales"), 0)
        ),
        "payments_received": currency(
            first_value(data, ("payments_received", "payments_received_mtd"), 0)
        ),
        "payment_count": first_value(
            data, ("payment_transaction_count", "transaction_count"), 0
        ),
        "inventory_cost": currency(
            first_value(
                data,
                ("inventory_cost_basis", "current_inventory_cost_basis"),
                0,
            )
        ),
        "new_cost": currency(
            first_value(data, ("new_inventory_cost", "new_cost_basis"), 0)
        ),
        "used_cost": currency(
            first_value(data, ("used_inventory_cost", "used_cost_basis"), 0)
        ),
        "inventory_units": first_value(
            data, ("inventory_units", "unit_count"), 0
        ),
    }


def vehicle_summary_row(item):
    return {
        "vehicle_id": item.get("vehicle_id") or item.get("id"),
        "vin": item.get("vin") or "—",
        "vehicle": item.get("vehicle")
        or item.get("vehicle_name")
        or "—",
        "acquisition_cost": currency_or_dash(item.get("acquisition_cost")),
        "transport_cost": currency_or_dash(item.get("transport_cost")),
        "recon_cost": currency_or_dash(
            first_value(item, ("recon_cost", "reconditioning_cost"), 0)
        ),
        "cost_basis": currency_or_dash(
            first_value(item, ("total_cost_basis", "cost_basis"), 0)
        ),
        "sale_price": currency_or_dash(
            first_value(item, ("sale_price", "total_amount"), None)
        ),
        "gross_profit": currency_or_dash(item.get("gross_profit")),
        "gross_profit_value": decimal_value(item.get("gross_profit")),
    }


def vehicle_summary_rows(payload):
    data = unwrap(payload)
    if isinstance(data, dict) and not isinstance(data.get("results"), list):
        return [vehicle_summary_row(data)] if data else []
    return [
        vehicle_summary_row(item)
        for item in list_results(payload)
        if isinstance(item, dict)
    ]
