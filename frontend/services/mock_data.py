from copy import deepcopy
from datetime import date, datetime, timezone


MOCK_CURRENT_USER = {
    "id": 1,
    "name": "Admin Profile",
    "email": "admin@autosource.com",
    "role": "admin",
}

MOCK_OVERVIEW = {
    "total_vehicles": 342,
    "vehicles_change_this_month": 12,
    "vehicle_status": {"available": 180, "in_transit": 45},
    "total_sales_invoice_ytd": 4_200_000,
    "payments_received_ytd": 3_800_000,
    "active_customer_count": 1_204,
}

MOCK_RECENT_INVOICES = [
    {
        "id": 1,
        "invoice_number": "INV-001",
        "customer_name": "John Doe",
        "total_amount": 35_000,
        "invoice_date": date(2026, 8, 24),
    },
    {
        "id": 2,
        "invoice_number": "INV-002",
        "customer_name": "Jane Smith",
        "total_amount": 42_500,
        "invoice_date": date(2026, 8, 23),
    },
    {
        "id": 3,
        "invoice_number": "INV-003",
        "customer_name": "Acme Corp",
        "total_amount": 85_000,
        "invoice_date": date(2026, 8, 22),
    },
]

MOCK_RECENT_PAYMENTS = [
    {
        "id": 1,
        "receipt_number": "REC-101",
        "invoice_number": "INV-001",
        "amount": 10_000,
        "method": "WIRE",
    },
    {
        "id": 2,
        "receipt_number": "REC-102",
        "invoice_number": "INV-002",
        "amount": 42_500,
        "method": "FINANCED",
    },
    {
        "id": 3,
        "receipt_number": "REC-103",
        "invoice_number": "INV-005",
        "amount": 5_000,
        "method": "CHECK",
    },
]

MOCK_EMPLOYEES = [
    {
        "id": 1,
        "name": "Sarah Connor",
        "email": "s.connor@autosource.com",
        "role": "agent",
    },
    {
        "id": 2,
        "name": "Mike Ehrmantraut",
        "email": "m.ehrmantraut@autosource.com",
        "role": "accountant",
    },
]


def overview():
    data = deepcopy(MOCK_OVERVIEW)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    return data


def invoices():
    return deepcopy(MOCK_RECENT_INVOICES)


def payments():
    return deepcopy(MOCK_RECENT_PAYMENTS)


def current_user(role="admin"):
    user = deepcopy(MOCK_CURRENT_USER)
    normalized_role = str(role).lower()
    if normalized_role in {"admin", "agent", "accountant"}:
        user["role"] = normalized_role
        user["name"] = f"{normalized_role.title()} Profile"
    return user


def initial_employees():
    return deepcopy(MOCK_EMPLOYEES)
