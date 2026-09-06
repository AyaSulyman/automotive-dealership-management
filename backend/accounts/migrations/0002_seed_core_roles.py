from django.db import migrations


def create_core_roles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    descriptions = {
        "admin": "Full access to all dealership modules.",
        "agent": "Access to inventory and customer modules.",
        "accountant": "Access to sales, payments, and finance modules.",
    }
    for name, description in descriptions.items():
        Role.objects.get_or_create(
            name=name,
            defaults={"description": description},
        )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [migrations.RunPython(create_core_roles, migrations.RunPython.noop)]
