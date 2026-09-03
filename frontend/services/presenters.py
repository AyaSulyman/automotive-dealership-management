from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re


ALLOWED_ROLES = {"admin", "agent", "accountant"}


def unwrap(payload):
    if isinstance(payload, dict) and payload.get("data") is not None:
        return payload["data"]
    return payload


def list_results(payload):
    value = unwrap(payload)
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get("results"), list):
        return value["results"]
    return []


def first_value(mapping, names, default=None):
    if not isinstance(mapping, dict):
        return default
    for name in names:
        value = mapping.get(name)
        if value is not None:
            return value
    return default


def number(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def format_number(value):
    return f"{number(value):,.0f}"


def format_currency(value, *, compact=False):
    amount = number(value)
    absolute = abs(amount)
    if compact and absolute >= 1_000_000:
        formatted = amount / Decimal("1000000")
        return f"${formatted:,.1f}M".replace(".0M", "M")
    if compact and absolute >= 1_000:
        formatted = amount / Decimal("1000")
        return f"${formatted:,.1f}K".replace(".0K", "K")
    return f"${amount:,.0f}"


def normalize_role(value):
    if isinstance(value, dict):
        value = value.get("slug") or value.get("name") or value.get("code")
    role = str(value or "").strip().lower()
    return role if role in ALLOWED_ROLES else ""


def display_role(value):
    role = normalize_role(value)
    return role.title() if role else "Employee"


def user_name(user):
    if not isinstance(user, dict):
        return "Employee Profile"
    direct = first_value(user, ("name", "full_name", "display_name"), "")
    combined = " ".join(
        str(part).strip()
        for part in (user.get("first_name"), user.get("last_name"))
        if part
    )
    return direct or combined or user.get("email") or "Employee Profile"


def user_identity(user):
    name = user_name(user)
    initials = "".join(part[0].upper() for part in name.split()[:2] if part)
    role = normalize_role(user.get("role") if isinstance(user, dict) else "")
    return {
        "name": name,
        "initials": initials or "EP",
        "role": role,
        "role_display": display_role(role),
    }


def _status_counts(overview):
    status = first_value(
        overview,
        ("vehicle_status", "vehicle_status_split", "vehicles_by_status"),
        {},
    )
    if not isinstance(status, dict):
        status = {}
    available = first_value(status, ("available", "AVAILABLE"), 0)
    in_transit = first_value(
        status, ("in_transit", "IN_TRANSIT", "inTransit"), 0
    )
    return number(available), number(in_transit)


def overview_context(payload):
    overview = unwrap(payload)
    if not isinstance(overview, dict):
        overview = {}
    available, in_transit = _status_counts(overview)
    status_total = available + in_transit
    availability_percent = (
        round(float(available / status_total * 100)) if status_total else 0
    )
    monthly_change = first_value(
        overview,
        (
            "vehicles_change_this_month",
            "vehicle_change_this_month",
            "monthly_vehicle_change",
        ),
        None,
    )
    change_value = number(monthly_change) if monthly_change is not None else None

    if change_value is None:
        change_text = "Current inventory"
        change_positive = False
    else:
        sign = "+" if change_value > 0 else ""
        change_text = f"↗ {sign}{format_number(change_value)} this month"
        change_positive = change_value >= 0

    return {
        "total_vehicles": format_number(
            first_value(overview, ("total_vehicles", "vehicle_count"), 0)
        ),
        "vehicles_change": change_text,
        "vehicles_change_positive": change_positive,
        "available": format_number(available),
        "in_transit": format_number(in_transit),
        "availability_percent": availability_percent,
        "total_sales": format_currency(
            first_value(
                overview,
                (
                    "total_sales_invoice_ytd",
                    "sales_invoice_ytd",
                    "total_sales_ytd",
                ),
                0,
            ),
            compact=True,
        ),
        "payments_received": format_currency(
            first_value(
                overview,
                ("payments_received_ytd", "total_payments_ytd"),
                0,
            ),
            compact=True,
        ),
        "active_customers": format_number(
            first_value(
                overview,
                ("active_customer_count", "active_customers", "customer_count"),
                0,
            )
        ),
        "updated_at": first_value(
            overview, ("updated_at", "last_updated"), None
        ),
    }


def _date_value(value):
    if isinstance(value, (date, datetime)):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return value


def invoice_rows(payload):
    rows = []
    for invoice in list_results(payload):
        if not isinstance(invoice, dict):
            continue
        customer = invoice.get("customer")
        if isinstance(customer, dict):
            customer = user_name(customer)
        rows.append(
            {
                "number": first_value(
                    invoice, ("invoice_number", "number", "id"), "—"
                ),
                "customer": invoice.get("customer_name") or customer or "—",
                "amount": format_currency(
                    first_value(
                        invoice, ("total_amount", "amount", "grand_total"), 0
                    )
                ),
                "date": _date_value(
                    first_value(
                        invoice, ("invoice_date", "date", "created_at"), None
                    )
                ),
            }
        )
    return rows


def payment_rows(payload):
    rows = []
    for payment in list_results(payload):
        if not isinstance(payment, dict):
            continue
        invoice = payment.get("invoice") or payment.get("sales_invoice")
        invoice_number = ""
        if isinstance(invoice, dict):
            invoice_number = invoice.get("invoice_number") or invoice.get("number")
        method = first_value(payment, ("method", "payment_method"), "Other")
        rows.append(
            {
                "receipt": first_value(
                    payment, ("receipt_number", "receipt", "id"), "—"
                ),
                "invoice": first_value(
                    payment, ("invoice_number", "invoice_ref"), ""
                )
                or invoice_number
                or "—",
                "amount": format_currency(
                    first_value(payment, ("amount", "payment_amount"), 0)
                ),
                "method": str(method).replace("_", " ").title(),
                "method_class": re.sub(
                    r"[^a-z0-9]+", "-", str(method).strip().lower()
                ).strip("-")
                or "other",
            }
        )
    return rows


def employee_rows(payload):
    rows = []
    for employee in list_results(payload):
        if not isinstance(employee, dict):
            continue
        role = normalize_role(employee.get("role"))
        rows.append(
            {
                "id": employee.get("id"),
                "name": user_name(employee),
                "email": employee.get("email") or "—",
                "role": role,
                "role_display": display_role(role),
            }
        )
    return rows


def filter_rows(rows, query):
    normalized = str(query or "").strip().lower()
    if not normalized:
        return rows
    return [
        row
        for row in rows
        if normalized in " ".join(str(value) for value in row.values()).lower()
    ]
