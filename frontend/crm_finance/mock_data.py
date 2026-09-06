from copy import deepcopy


MOCK_CUSTOMERS = [
    {
        "id": 89234,
        "customer_number": "CUS-89234",
        "full_name": "Elena Rodriguez",
        "id_type": "NATIONAL_ID",
        "id_number": "TX-492-881-A",
        "phone": "(555) 019-2834",
        "email": "elena.r@example.com",
        "address": "18 Westbrook Avenue",
        "status": "ACTIVE",
        "created_at": "2026-07-12",
    },
    {
        "id": 89235,
        "customer_number": "CUS-89235",
        "full_name": "James Duncan",
        "id_type": "DL",
        "id_number": "TX-112-445-B",
        "phone": "(555) 882-9912",
        "email": "j.duncan@corp.com",
        "address": "42 Market Street",
        "status": "LEAD",
        "created_at": "2026-07-18",
    },
    {
        "id": 89236,
        "customer_number": "CUS-89236",
        "full_name": "Evelyn Jenkins",
        "id_type": "PASSPORT",
        "id_number": "P-440291",
        "phone": "(555) 230-7741",
        "email": "e.jenkins@example.com",
        "address": "9 Cedar Drive",
        "status": "VIP",
        "created_at": "2026-08-04",
    },
    {
        "id": 89237,
        "customer_number": "CUS-89237",
        "full_name": "Michael Chen",
        "id_type": "NATIONAL_ID",
        "id_number": "ID-786-552",
        "phone": "(555) 661-0950",
        "email": "m.chen@example.com",
        "address": "77 Lakeview Road",
        "status": "ACTIVE",
        "created_at": "2026-08-21",
    },
]

MOCK_INVOICES = [
    {
        "id": 4402,
        "invoice_number": "INV-4402",
        "customer_id": 89237,
        "customer_name": "Michael Chen",
        "vehicle_id": 1001,
        "vehicle": "2024 Toyota Camry SE",
        "vin": "4T1B31HK2RU123456",
        "total_amount": 32500,
        "balance_due": 12500,
        "status": "OPEN",
    },
    {
        "id": 8891,
        "invoice_number": "INV-8891",
        "customer_id": 89236,
        "customer_name": "Evelyn Jenkins",
        "vehicle_id": 1002,
        "vehicle": "2023 Audi Q5 Premium",
        "vin": "WA1AAAFZ7M109283",
        "total_amount": 34175.88,
        "balance_due": 24175.88,
        "status": "OPEN",
    },
    {
        "id": 7305,
        "invoice_number": "INV-7305",
        "customer_id": 89234,
        "customer_name": "Elena Rodriguez",
        "vehicle_id": 1003,
        "vehicle": "2022 Honda Civic EX",
        "vin": "2HGFE2F50NH612804",
        "total_amount": 24800,
        "balance_due": 0,
        "status": "PAID",
    },
]

MOCK_PAYMENTS = [
    {
        "id": 9821,
        "receipt_number": "REC-9821",
        "invoice_id": 4402,
        "invoice_number": "INV-4402",
        "customer_name": "Michael Chen",
        "vehicle": "2024 Toyota Camry SE",
        "amount": 12500,
        "method": "TRANSFER",
        "reference_number": "TRX-664190",
        "paid_at": "2026-08-24T14:30:00+00:00",
        "recorded_by_name": "Admin Profile",
        "balance_after": 0,
    },
    {
        "id": 9819,
        "receipt_number": "REC-9819",
        "invoice_id": 8891,
        "invoice_number": "INV-8891",
        "customer_name": "Evelyn Jenkins",
        "vehicle": "2023 Audi Q5 Premium",
        "amount": 10000,
        "method": "CARD",
        "reference_number": "CARD-1182",
        "paid_at": "2026-08-20T10:15:00+00:00",
        "recorded_by_name": "Accountant Profile",
        "balance_after": 24175.88,
    },
    {
        "id": 9815,
        "receipt_number": "REC-9815",
        "invoice_id": 7305,
        "invoice_number": "INV-7305",
        "customer_name": "Elena Rodriguez",
        "vehicle": "2022 Honda Civic EX",
        "amount": 24800,
        "method": "CASH",
        "reference_number": "",
        "paid_at": "2026-08-16T09:10:00+00:00",
        "recorded_by_name": "Admin Profile",
        "balance_after": 0,
    },
]

MOCK_SCHEDULES = [
    {
        "id": 3101,
        "invoice_id": 8891,
        "invoice_number": "INV-8891",
        "installment_number": 1,
        "due_date": "2026-09-15",
        "amount_due": 6043.97,
        "amount_paid": 0,
        "status": "PENDING",
    },
    {
        "id": 3102,
        "invoice_id": 8891,
        "invoice_number": "INV-8891",
        "installment_number": 2,
        "due_date": "2026-10-15",
        "amount_due": 6043.97,
        "amount_paid": 0,
        "status": "PENDING",
    },
]

MOCK_FINANCING = [
    {
        "id": 7101,
        "invoice_id": 8891,
        "invoice_number": "INV-8891",
        "lender_name": "Metro Auto Finance",
        "down_payment": 10000,
        "term_months": 4,
        "interest_rate": 0.0625,
        "monthly_payment": 6043.97,
        "status": "ACTIVE",
    }
]

MOCK_CUSTOMER_HISTORY = {
    89234: [
        {
            "type": "invoice",
            "reference": "INV-7305",
            "description": "Vehicle sale",
            "date": "2026-08-16",
            "amount": 24800,
        },
        {
            "type": "payment",
            "reference": "REC-9815",
            "description": "Cash payment",
            "date": "2026-08-16",
            "amount": 24800,
        },
    ],
    89236: [
        {
            "type": "invoice",
            "reference": "INV-8891",
            "description": "Vehicle sale",
            "date": "2026-08-20",
            "amount": 34175.88,
        },
        {
            "type": "payment",
            "reference": "REC-9819",
            "description": "Card payment",
            "date": "2026-08-20",
            "amount": 10000,
        },
    ],
}

MOCK_FINANCE_OVERVIEW = {
    "total_sales_mtd": 1245000,
    "payments_received": 980500,
    "payment_transaction_count": 42,
    "inventory_cost_basis": 3105200,
    "new_inventory_cost": 2400000,
    "used_inventory_cost": 705200,
    "inventory_units": 114,
}

MOCK_VEHICLE_SUMMARIES = [
    {
        "vehicle_id": 1001,
        "vin": "4T1B31HK2RU123456",
        "vehicle": "2024 Toyota Camry SE",
        "acquisition_cost": 24750,
        "transport_cost": 450,
        "recon_cost": 300,
        "total_cost_basis": 25500,
        "sale_price": 32500,
        "gross_profit": 7000,
    },
    {
        "vehicle_id": 1002,
        "vin": "WA1AAAFZ7M109283",
        "vehicle": "2023 Audi Q5 Premium",
        "acquisition_cost": 27000,
        "transport_cost": 650,
        "recon_cost": 850,
        "total_cost_basis": 28500,
        "sale_price": 34175.88,
        "gross_profit": 5675.88,
    },
    {
        "vehicle_id": 1003,
        "vin": "2HGFE2F50NH612804",
        "vehicle": "2022 Honda Civic EX",
        "acquisition_cost": 19100,
        "transport_cost": 350,
        "recon_cost": 750,
        "total_cost_basis": 20200,
        "sale_price": 24800,
        "gross_profit": 4600,
    },
]


def customers():
    return deepcopy(MOCK_CUSTOMERS)


def invoices():
    return deepcopy(MOCK_INVOICES)


def payments():
    return deepcopy(MOCK_PAYMENTS)


def schedules():
    return deepcopy(MOCK_SCHEDULES)


def financing_accounts():
    return deepcopy(MOCK_FINANCING)


def customer_history(customer_id):
    try:
        key = int(customer_id)
    except (TypeError, ValueError):
        key = customer_id
    return deepcopy(MOCK_CUSTOMER_HISTORY.get(key, []))


def finance_overview():
    return deepcopy(MOCK_FINANCE_OVERVIEW)


def vehicle_summaries():
    return deepcopy(MOCK_VEHICLE_SUMMARIES)
