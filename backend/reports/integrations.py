"""
Integration hooks into Person 1's inventory domain for dashboard/report
figures Person 2 doesn't own the data for (total vehicle count, vehicle
status split). No-op stubs for now -- swap the body for a real query once
the catalog/vehicles app lands, without changing the call site in views.py.
"""


def get_inventory_snapshot():
    """TODO once catalog app exists:
        from catalog.models import Vehicle
        return {
            "total_vehicles": Vehicle.objects.count(),
            "status_breakdown": dict(Vehicle.objects.values_list("status").annotate(...)),
        }
    """
    return {"total_vehicles": None, "status_breakdown": None}
