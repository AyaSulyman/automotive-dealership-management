"""Read-only reporting queries against the shared inventory domain."""

from django.db.models import Count, Sum
from django.utils import timezone


def _current_inventory():
    from inventory.models import Vehicle

    return Vehicle.objects.exclude(status="SOLD")


def get_inventory_snapshot():
    """Return inventory totals used by the staff dashboard."""
    from inventory.models import Vehicle

    status_rows = Vehicle.objects.values("status").annotate(total=Count("id"))
    month_start = timezone.now().replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    return {
        "total_vehicles": Vehicle.objects.count(),
        "status_breakdown": {
            row["status"]: row["total"] for row in status_rows
        },
        "vehicles_change_this_month": Vehicle.objects.filter(
            created_at__gte=month_start
        ).count(),
    }


def get_inventory_cost_basis_split():
    """Return the cost basis of unsold inventory, split by condition."""
    vehicles = _current_inventory()
    new_cost = vehicles.filter(condition="NEW").aggregate(
        total=Sum("total_cost_basis")
    )["total"] or 0
    used_cost = vehicles.filter(condition="USED").aggregate(
        total=Sum("total_cost_basis")
    )["total"] or 0
    return {
        "new_cost_basis": str(new_cost),
        "used_cost_basis": str(used_cost),
        "current_inventory_cost_basis": str(new_cost + used_cost),
        "inventory_units": vehicles.count(),
    }


def get_work_order_costs_mtd():
    """Use recorded vehicle reconditioning cost until work orders are added."""
    month_start = timezone.now().replace(day=1).date()
    total = _current_inventory().filter(
        created_at__date__gte=month_start
    ).aggregate(total=Sum("recon_cost"))["total"] or 0
    return str(total)


def get_vehicle_cost_basis(vehicle_id):
    from inventory.models import Vehicle

    vehicle = Vehicle.objects.filter(pk=vehicle_id).only(
        "total_cost_basis"
    ).first()
    return vehicle.total_cost_basis if vehicle else None


def get_vehicle_financial_data(identifier):
    """Resolve either a numeric vehicle id or a VIN for the report screen."""
    from inventory.models import Vehicle

    query = str(identifier or "").strip()
    vehicle = None
    if query.isdigit():
        vehicle = Vehicle.objects.filter(pk=int(query)).first()
    if vehicle is None and query:
        vehicle = Vehicle.objects.filter(vin__iexact=query).first()
    if vehicle is None:
        return None
    return {
        "vehicle_id": vehicle.pk,
        "vin": vehicle.vin,
        "vehicle_name": f"{vehicle.year} {vehicle.make} {vehicle.model}".strip(),
        "acquisition_cost": str(vehicle.acquisition_cost),
        "transport_cost": str(vehicle.transport_cost),
        "recon_cost": str(vehicle.recon_cost),
        "total_cost_basis": str(vehicle.total_cost_basis),
    }
