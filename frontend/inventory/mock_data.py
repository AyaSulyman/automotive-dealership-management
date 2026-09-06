"""
Temporary preview data for the Inventory & Procurement page.

The views use this data only while ``ADMS_PREVIEW_MODE`` is enabled. Once an
``ADMS_API_BASE_URL`` is configured, the same views call the REST backend
through the Python service layer and keep the templates unchanged.

Preview values mirror the backend's vehicle status and condition choices.
"""

STATUS_CHOICES = [
    {'value': 'IN_TRANSIT', 'label': 'In Transit', 'style': 'badge-blue'},
    {'value': 'IN_STOCK', 'label': 'In Stock', 'style': 'badge-purple'},
    {'value': 'AVAILABLE', 'label': 'Available', 'style': 'badge-green'},
    {'value': 'RESERVED', 'label': 'Reserved', 'style': 'badge-amber'},
    {'value': 'SOLD', 'label': 'Sold', 'style': 'badge-gray'},
]

_STATUS_STYLE_BY_VALUE = {s['value']: s for s in STATUS_CHOICES}

CONDITION_CHOICES = ['NEW', 'USED']


def get_vehicles():
    """Mirrors the `vehicle` table in the ERD (branch_id removed per scope)."""
    vehicles = [
        {
            'id': 'V-1042',
            'vin': '1G1RC6647BU123456',
            'make': 'Chevrolet',
            'model': 'Malibu',
            'year': 2021,
            'trim': 'LT',
            'condition': 'USED',
            'purchase_order': 'PO-8821',
            'status': 'AVAILABLE',
            'status_label': 'In Stock',
            'acquisition_cost': 21000.00,
            'transport_cost': 1200.00,
            'recon_cost': 2300.00,
            'cost_basis': 24500.00,
        },
        {
            'id': 'V-1043',
            'vin': '2T1BURHE3HC123456',
            'make': 'Toyota',
            'model': 'Corolla',
            'year': 2022,
            'trim': 'SE',
            'condition': 'USED',
            'purchase_order': 'PO-8822',
            'status': 'IN_TRANSIT',
            'status_label': 'In Transit',
            'acquisition_cost': 29000.00,
            'transport_cost': 1500.00,
            'recon_cost': 700.00,
            'cost_basis': 31200.00,
        },
        {
            'id': 'V-1044',
            'vin': 'JHMCS16428C123456',
            'make': 'Honda',
            'model': 'Civic',
            'year': 2019,
            'trim': 'EX',
            'condition': 'USED',
            'purchase_order': 'PO-8819',
            'status': 'SOLD',
            'status_label': 'Sold',
            'acquisition_cost': 15500.00,
            'transport_cost': 900.00,
            'recon_cost': 2500.00,
            'cost_basis': 18900.00,
        },
    ]
    for v in vehicles:
        v['status_style'] = _STATUS_STYLE_BY_VALUE.get(v['status'], {}).get('style', 'badge-gray')
    return vehicles


def get_vendors():
    """Mirrors the `vendor` table in the ERD."""
    return [
        {
            'id': 'VD-101',
            'name': 'Coastal Auto Auctions',
            'contact_person': 'Rania Haddad',
            'phone': '+961 1 555 210',
            'email': 'rania@coastalauctions.com',
            'address': '18 Harbor Road',
            'is_active': True,
        },
        {
            'id': 'VD-102',
            'name': 'Midway Wholesale Motors',
            'contact_person': 'Omar Fakhoury',
            'phone': '+961 1 555 482',
            'email': 'omar@midwaywholesale.com',
            'address': '55 Market Street',
            'is_active': True,
        },
        {
            'id': 'VD-103',
            'name': 'Northline Fleet Sourcing',
            'contact_person': 'Dana Saab',
            'phone': '+961 1 555 903',
            'email': 'dana@northlinefleet.com',
            'address': '9 Northline Avenue',
            'is_active': False,
        },
    ]


def get_purchase_orders():
    """Mirrors the `purchase_order` table in the ERD."""
    return [
        {
            'id': 'PO-8821',
            'vendor': 'Coastal Auto Auctions',
            'order_date': '2026-08-12',
            'expected_date': '2026-08-19',
            'status': 'RECEIVED',
            'status_label': 'Received',
            'status_style': 'badge-green',
        },
        {
            'id': 'PO-8822',
            'vendor': 'Midway Wholesale Motors',
            'order_date': '2026-08-20',
            'expected_date': '2026-08-27',
            'status': 'PENDING',
            'status_label': 'Pending',
            'status_style': 'badge-amber',
        },
        {
            'id': 'PO-8819',
            'vendor': 'Coastal Auto Auctions',
            'order_date': '2026-07-30',
            'expected_date': '2026-08-05',
            'status': 'RECEIVED',
            'status_label': 'Received',
            'status_style': 'badge-green',
        },
    ]
