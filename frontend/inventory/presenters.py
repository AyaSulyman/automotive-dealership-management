from decimal import Decimal, InvalidOperation

from services.presenters import first_value, list_results, unwrap


STATUS_LABELS = {
    "IN_TRANSIT": "In Transit",
    "RECEIVED": "Received",
    "UNDER_RECONDITIONING": "Under Reconditioning",
    "AVAILABLE": "Available",
    "RESERVED": "Reserved",
    "SOLD": "Sold",
    "RETURNED": "Returned",
    "PENDING": "Pending",
    "CLOSED": "Closed",
}

STATUS_STYLES = {
    "IN_TRANSIT": "badge-blue",
    "RECEIVED": "badge-purple",
    "UNDER_RECONDITIONING": "badge-amber",
    "AVAILABLE": "badge-green",
    "RESERVED": "badge-amber",
    "SOLD": "badge-gray",
    "RETURNED": "badge-red",
    "PENDING": "badge-amber",
    "CLOSED": "badge-gray",
}


def _number(value):
    try:
        return Decimal(str(value or 0))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


def money(value):
    return f"${_number(value):,.2f}"


def status_label(value):
    status = str(value or "").upper()
    return STATUS_LABELS.get(status, status.replace("_", " ").title() or "Unknown")


def status_style(value):
    return STATUS_STYLES.get(str(value or "").upper(), "badge-gray")


def normalize_vehicle(vehicle):
    if not isinstance(vehicle, dict):
        return {}
    purchase_order = vehicle.get("purchase_order")
    if isinstance(purchase_order, dict):
        purchase_order = first_value(
            purchase_order, ("po_number", "number", "id"), "—"
        )
    acquisition = _number(vehicle.get("acquisition_cost"))
    transport = _number(vehicle.get("transport_cost"))
    recon = _number(vehicle.get("recon_cost"))
    cost_basis = first_value(
        vehicle, ("total_cost_basis", "cost_basis"), None
    )
    if cost_basis is None:
        cost_basis = acquisition + transport + recon
    status = str(vehicle.get("status") or "").upper()
    return {
        **vehicle,
        "id": first_value(vehicle, ("id", "vehicle_id"), "—"),
        "vin": vehicle.get("vin") or "—",
        "make": vehicle.get("make") or "—",
        "model": vehicle.get("model") or "—",
        "year": vehicle.get("year") or "—",
        "trim": vehicle.get("trim") or "",
        "condition": vehicle.get("condition") or "—",
        "purchase_order": purchase_order
        or vehicle.get("purchase_order_id")
        or "—",
        "status": status,
        "status_label": vehicle.get("status_label") or status_label(status),
        "status_style": vehicle.get("status_style") or status_style(status),
        "acquisition_cost_display": money(acquisition),
        "transport_cost_display": money(transport),
        "recon_cost_display": money(recon),
        "cost_basis_display": money(cost_basis),
    }


def normalize_vendor(vendor):
    if not isinstance(vendor, dict):
        return {}
    active = bool(vendor.get("is_active", True))
    return {
        **vendor,
        "id": first_value(vendor, ("id", "vendor_id"), "—"),
        "name": vendor.get("name") or "—",
        "contact_name": vendor.get("contact_name") or "—",
        "phone": vendor.get("phone") or "—",
        "email": vendor.get("email") or "—",
        "payment_terms": vendor.get("payment_terms") or "—",
        "is_active": active,
        "status_label": "Active" if active else "Inactive",
        "status_style": "badge-green" if active else "badge-gray",
    }


def normalize_purchase_order(purchase_order):
    if not isinstance(purchase_order, dict):
        return {}
    vendor = purchase_order.get("vendor")
    if isinstance(vendor, dict):
        vendor = first_value(vendor, ("name", "vendor_name", "id"), "—")
    status = str(purchase_order.get("status") or "").upper()
    return {
        **purchase_order,
        "id": first_value(
            purchase_order, ("id", "po_number", "number"), "—"
        ),
        "vendor": vendor
        or purchase_order.get("vendor_name")
        or purchase_order.get("vendor_id")
        or "—",
        "order_date": purchase_order.get("order_date") or "—",
        "expected_date": purchase_order.get("expected_date") or "—",
        "status": status,
        "status_label": purchase_order.get("status_label")
        or status_label(status),
        "status_style": purchase_order.get("status_style")
        or status_style(status),
    }


def page_results(payload, normalizer, *, requested_page=1, page_size=10):
    value = unwrap(payload)
    rows = [normalizer(item) for item in list_results(payload)]
    if isinstance(value, dict):
        count = int(value.get("count", len(rows)) or 0)
        has_previous = bool(value.get("previous")) or requested_page > 1
        has_next = bool(value.get("next")) or requested_page * page_size < count
    else:
        count = len(rows)
        has_previous = requested_page > 1
        has_next = requested_page * page_size < count
    return rows, count, has_previous, has_next

