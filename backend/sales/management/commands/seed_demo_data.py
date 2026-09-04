"""
Seeds a full, realistic chain of demo data so every Person 2 endpoint can
be tested immediately via Swagger UI / Postman without manually creating
records one at a time first.

Usage:
    python manage.py seed_demo_data            # add another demo deal
    python manage.py seed_demo_data --reset    # wipe existing demo data first

Order matters here -- each step depends on the previous one existing,
mirroring the real dependency chain your APIs enforce:
    groups -> users -> tax rule -> sales invoice (DRAFT) -> discount
    -> trade-in -> apply-credit -> finalize -> payment -> schedule
    -> financing account -> statement
"""
import datetime
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.utils import timezone

from payments.models import FinancingAccount, Payment, PaymentSchedule, Statement
from reports.models import AuditLog
from sales.models import Discount, SalesInvoice, TaxRule, TradeIn


class Command(BaseCommand):
    help = "Seed demo data for testing Person 2 APIs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Delete existing demo data (sales/payments/reports rows) before seeding.",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self.stdout.write("Resetting existing data...")
            AuditLog.objects.all().delete()
            Statement.objects.all().delete()
            Payment.objects.all().delete()
            PaymentSchedule.objects.all().delete()
            FinancingAccount.objects.all().delete()
            Discount.objects.all().delete()
            TradeIn.objects.all().delete()
            SalesInvoice.objects.all().delete()
            TaxRule.objects.all().delete()

        # 1. Groups -----------------------------------------------------
        self.stdout.write("Creating groups (admin, agent, accountant)...")
        role_names = ["admin", "agent", "accountant"]
        groups = {name: Group.objects.get_or_create(name=name)[0] for name in role_names}

        # 2. Users --------------------------------------------------------
        self.stdout.write("Creating demo users (password: testpass123)...")
        users = {}
        for username, role, is_super in [
            ("admin1", "admin", True),
            ("agent1", "agent", False),
            ("acct1", "accountant", False),
        ]:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"is_superuser": is_super, "is_staff": is_super},
            )
            if created:
                user.set_password("testpass123")
                user.save()
            user.groups.add(groups[role])
            users[role] = user

        admin_user, agent_user, accountant_user = users["admin"], users["agent"], users["accountant"]

        # 3. Tax rule -----------------------------------------------------
        self.stdout.write("Creating a tax rule (6.25%)...")
        tax_rule, _ = TaxRule.objects.get_or_create(
            jurisdiction="TX-State", defaults={"rate": Decimal("0.0625"), "applies_to": "TRANSACTION_TYPE"},
        )

        # 4. Sales invoice (DRAFT) -----------------------------------------
        self.stdout.write("Creating a Sales Invoice (DRAFT)...")
        invoice = SalesInvoice(
            customer_id=1001, vehicle_id=2001, salesperson=agent_user,
            selling_price=Decimal("30000"), branch_id=1,
        )
        invoice.recompute_totals(tax_rate=tax_rule.rate)
        invoice.save()

        # 5. Discount -------------------------------------------------------
        self.stdout.write("Adding a discount...")
        discount_amount = Decimal("500")
        Discount.objects.create(
            invoice=invoice, discount_type="FIXED", amount=discount_amount, reason="Demo loyalty discount",
        )
        invoice.discount_amount = invoice.discount_amount + discount_amount
        invoice.recompute_totals(tax_rate=tax_rule.rate)
        invoice.save()

        # 6. Trade-in + apply-credit -----------------------------------------
        self.stdout.write("Capturing a trade-in and crediting it to the invoice...")
        trade_in = TradeIn.objects.create(
            customer_id=1001, vin="1HGCM82633A004352", make="Honda", model="Accord",
            year=2019, mileage=45000, condition="GOOD", appraised_value=Decimal("4000"),
            appraised_by=agent_user,
        )
        trade_in.credited_invoice = invoice
        trade_in.credited_reference = f"TRD-{trade_in.pk:03d}-DEMO"
        trade_in.save(update_fields=["credited_invoice", "credited_reference", "updated_at"])
        invoice.trade_in_credit = invoice.trade_in_credit + trade_in.appraised_value
        invoice.recompute_totals(tax_rate=tax_rule.rate)
        invoice.save()

        # 7. Finalize -------------------------------------------------------
        self.stdout.write("Finalizing the deal...")
        year = timezone.now().year
        invoice.invoice_number = f"INV-{year}-DEMO01"
        invoice.sale_date = timezone.now().date()
        invoice.status = "OPEN"
        invoice.recompute_totals(tax_rate=tax_rule.rate)
        invoice.save()
        AuditLog.objects.create(user=agent_user, action="UPDATE", entity_type="SalesInvoice", entity_id=invoice.pk, changes={"status": "OPEN"})

        # 8. Payment ----------------------------------------------------------
        self.stdout.write("Recording a payment...")
        payment = Payment.objects.create(
            invoice=invoice, amount=Decimal("5000"), method="CASH", receipt_number=f"RCT-{year}-DEMO01",
            paid_at=timezone.now(), recorded_by=accountant_user,
        )
        invoice.balance_due = invoice.balance_due - payment.amount
        invoice.save(update_fields=["balance_due", "updated_at"])
        AuditLog.objects.create(user=accountant_user, action="CREATE", entity_type="Payment", entity_id=payment.pk, changes={"amount": str(payment.amount)})

        # 9. Payment schedule ---------------------------------------------------
        self.stdout.write("Generating a payment schedule for the remaining balance...")
        remaining = invoice.balance_due
        installments = 5
        per = (remaining / installments).quantize(remaining)
        running = 0
        today = datetime.date.today()
        for i in range(1, installments + 1):
            amt = per if i < installments else remaining - running
            running += amt
            PaymentSchedule.objects.create(
                invoice=invoice, installment_number=i,
                due_date=today + datetime.timedelta(days=30 * i), amount_due=amt,
            )

        # 10. Financing account ---------------------------------------------------
        self.stdout.write("Creating a financing account...")
        FinancingAccount.objects.create(
            invoice=invoice, lender_name="Demo Capital", down_payment=Decimal("5000"),
            term_months=48, interest_rate=Decimal("0.0599"),
        )

        # 11. Statement ---------------------------------------------------------
        self.stdout.write("Generating a customer statement...")
        Statement.objects.create(
            customer_id=1001,
            period_start=today.replace(month=1, day=1),
            period_end=today,
            summary={
                "invoice_count": 1,
                "invoices_total": str(invoice.total_amount),
                "payment_count": 1,
                "payments_total": str(payment.amount),
                "outstanding_balance": str(invoice.balance_due),
                "invoices": [{"id": invoice.id, "invoice_number": invoice.invoice_number, "sale_date": str(invoice.sale_date), "total_amount": str(invoice.total_amount)}],
                "payments": [{"id": payment.id, "receipt_number": payment.receipt_number, "paid_at": str(payment.paid_at), "amount": str(payment.amount)}],
            },
        )

        # 12. Issue JWTs for convenience ------------------------------------------
        from rest_framework_simplejwt.tokens import RefreshToken

        self.stdout.write(self.style.SUCCESS("\nDemo data created successfully."))
        self.stdout.write(self.style.SUCCESS(f"  Sales Invoice id={invoice.id}  invoice_number={invoice.invoice_number}  customer_id=1001  vehicle_id=2001"))
        self.stdout.write(self.style.SUCCESS(f"  Payment id={payment.id}  Trade-In id={trade_in.id}"))
        self.stdout.write("\nAccess tokens (paste into Postman's bearerToken variable or Swagger's Authorize button):\n")
        for role, user in users.items():
            token = RefreshToken.for_user(user)
            self.stdout.write(f"  {role:11s} ({user.username}): {token.access_token}")
