"""
Seeds Person 1's demo data: identity (roles/branch/admin via seed_accounts
logic), one vendor, one purchase order, vehicles with computed cost basis,
a customer, valuations, and an attached document. Idempotent.

Usage:
    python manage.py seed_person1
    python manage.py seed_person1 --reset   # drop Person 1 inventory data, then re-seed
"""
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from accounts.models import Branch, Role, UserProfile
from customers.models import Customer
from inventory.models import Document, PurchaseOrder, Vehicle, VehicleMedia, VehicleValuation, Vendor


class Command(BaseCommand):
    help = "Seed demo data for Person 1 APIs (vendors, POs, vehicles, customers, documents)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Delete existing Person 1 entities before re-seeding.",
        )

    def handle(self, *args, **options):
        seller, _ = User.objects.get_or_create(
            username="admin", defaults={"email": "admin@adms.com", "is_superuser": True, "is_staff": True},
        )

        if options["reset"]:
            self.stdout.write("Resetting Person 1 data...")
            Document.objects.all().delete()
            VehicleValuation.objects.all().delete()
            VehicleMedia.objects.all().delete()
            Vehicle.objects.all().delete()
            PurchaseOrder.objects.all().delete()
            Vendor.objects.all().delete()
            Customer.objects.all().delete()

        # Identity ---------------------------------------------------------
        role_admin, _ = Role.objects.get_or_create(name="admin")
        branch, _ = Branch.objects.get_or_create(
            name="Main Showroom", defaults={"address": "1 Auto Plaza Drive", "phone": "+1-555-0100"},
        )
        UserProfile.objects.get_or_create(user=seller, defaults={"role": role_admin, "branch": branch})

        # Vendor -------------------------------------------------------------
        vendor, _ = Vendor.objects.get_or_create(
            name="Star Motors LLC",
            defaults={
                "contact_person": "Bob Wilson", "email": "bob@starmotors.com",
                "phone": "+1-555-0101", "address": "4500 Commerce St",
            },
        )

        # Purchase order -------------------------------------------------------
        po, _ = PurchaseOrder.objects.get_or_create(
            vendor=vendor, order_date="2026-09-01",
            defaults={"expected_date": "2026-09-20", "notes": "Initial stocking order"},
        )

        # Vehicles ---------------------------------------------------------------
        vehicle_a, _ = Vehicle.objects.get_or_create(
            vin="1HGCM82633A123457",
            defaults={
                "make": "Honda", "model": "Accord", "year": 2021, "trim": "EX",
                "condition": "USED", "status": "AVAILABLE", "branch": branch,
                "purchase_order": po, "acquisition_cost": Decimal("15000"),
                "transport_cost": Decimal("500"), "recon_cost": Decimal("1000"),
                "selling_price": Decimal("22500"),
            },
        )
        vehicle_a.compute_cost_basis()
        vehicle_a.save(update_fields=["total_cost_basis"])

        vehicle_b, _ = Vehicle.objects.get_or_create(
            vin="2FMDK3GC8FBA12345",
            defaults={
                "make": "Ford", "model": "Explorer", "year": 2020, "trim": "XLT",
                "condition": "USED", "status": "IN_STOCK", "branch": branch,
                "purchase_order": po, "acquisition_cost": Decimal("18000"),
                "transport_cost": Decimal("400"), "recon_cost": Decimal("600"),
                "selling_price": Decimal("26500"),
            },
        )
        vehicle_b.compute_cost_basis()
        vehicle_b.save(update_fields=["total_cost_basis"])

        # Valuation ----------------------------------------------------------------
        existing = VehicleValuation.objects.filter(vehicle=vehicle_a).first()
        if existing:
            existing.value = Decimal("21000")
            existing.source = "MANUAL"
            existing.notes = "Fair condition"
            existing.appraised_by = seller
            existing.save()
        else:
            VehicleValuation.objects.create(
                vehicle=vehicle_a, value=Decimal("21000"), source="MANUAL",
                notes="Fair condition", appraised_by=seller,
            )

        # Customer ------------------------------------------------------------------
        customer, _ = Customer.objects.get_or_create(
            first_name="Jane", last_name="Doe", email="jane@example.com",
            defaults={"phone": "+1-555-1234", "city": "Austin", "state": "TX", "created_by": seller},
        )

        # Document (small in-memory file so no zip/upload needed) ----------------------
        Document.objects.get_or_create(
            related_type="VEHICLE", related_id=vehicle_a.pk, doc_type="TITLE",
            defaults={
                "file": ContentFile(b"dummy title document", name="title-seed.txt"),
                "original_filename": "title-seed.txt", "uploaded_by": seller,
            },
        )

        self.stdout.write(self.style.SUCCESS(
            "Person 1 demo data seeded: 1 vendor, 1 PO, 2 vehicles, 1 customer, 1 valuation, 1 document."
        ))
        self.stdout.write(self.style.SUCCESS(
            f"  Vendor={vendor.name}  PO={po.po_number}  Vehicle A={vehicle_a.vin} (cost {vehicle_a.total_cost_basis})"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"  Customer={customer.id} {customer.first_name} {customer.last_name}"
        ))

        from rest_framework_simplejwt.tokens import RefreshToken

        token = RefreshToken.for_user(seller)
        self.stdout.write(f"\nAdmin access token (paste into Swagger Authorize): {token.access_token}")