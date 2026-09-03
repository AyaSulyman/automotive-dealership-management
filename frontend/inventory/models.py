"""
Intentionally empty for now.

The Django models for `Vehicle`, `Vendor` and `PurchaseOrder` will live here
once the backend team builds them, matching the ADMS ERD:
  - vehicle(id, vin, make, model, year, trim, condition, status,
            purchase_order_id, acquisition_cost, transport_cost, recon_cost)
  - vendor(id, name, contact_name, phone, email, payment_terms, is_active)
  - purchase_order(id, po_number, vendor_id, order_date, status)

Until then, inventory/mock_data.py stands in so the templates and views
can be built and reviewed independently of the backend.
"""
