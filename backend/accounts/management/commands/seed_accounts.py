"""
Seeds Person 1's identity data: the three roles, a default branch, an admin
superuser, and UserProfiles for every existing user whose role is already
known (either via Django Groups from Person 2's seed_demo_data, or by being
the superuser).

Usage:
    python manage.py seed_accounts
    python manage.py seed_accounts --reset   # drop profiles first, then re-seed

Idempotent: safe to run repeatedly.
"""
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from accounts.models import Branch, Role, UserProfile


class Command(BaseCommand):
    help = "Seed roles, a default branch, an admin user, and UserProfiles."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Delete existing UserProfiles before re-seeding.",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self.stdout.write("Resetting existing profiles...")
            UserProfile.objects.all().delete()

        # 1. Roles -----------------------------------------------------
        self.stdout.write("Creating roles (admin, agent, accountant)...")
        roles = {}
        for name in ["admin", "agent", "accountant"]:
            role, _ = Role.objects.get_or_create(
                name=name,
                defaults={"description": f"Dealership {name} role."},
            )
            roles[name] = role

        # 2. Branch -----------------------------------------------------
        branch, _ = Branch.objects.get_or_create(
            name="Main Showroom",
            defaults={"address": "1 Auto Plaza Drive", "phone": "+1-555-0100"},
        )

        # 3. Admin superuser ---------------------------------------------
        self.stdout.write("Ensuring 'admin' superuser exists (password: admin123)...")
        admin_user, created = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@adms.com", "is_superuser": True, "is_staff": True},
        )
        if created:
            admin_user.set_password("admin123")
            admin_user.save()

        # 4. Profiles -----------------------------------------------------
        self.stdout.write("Linking profiles for known roles...")
        UserProfile.objects.get_or_create(
            user=admin_user, defaults={"role": roles["admin"], "branch": branch},
        )

        known_roles = {
            username: roles[name] for username, name in [
                ("admin1", "admin"),
                ("agent1", "agent"),
                ("acct1", "accountant"),
            ]
        }
        for username, role in known_roles.items():
            user = User.objects.filter(username=username).first()
            if user is None:
                continue
            profile, created = UserProfile.objects.get_or_create(
                user=user, defaults={"role": role, "branch": branch},
            )
            if created:
                self.stdout.write(f"  Profile created for {username} -> {role.name}")

        self.stdout.write(self.style.SUCCESS(
            "Accounts seeded: 3 roles, 1 branch, admin superuser, profiles created."
        ))