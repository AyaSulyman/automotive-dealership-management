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


def get_inventory_cost_basis_split():
    """TODO once catalog app exists:
        from catalog.models import Vehicle
        return {
            "new_cost_basis": Vehicle.objects.filter(condition="NEW").aggregate(...),
            "used_cost_basis": Vehicle.objects.filter(condition="USED").aggregate(...),
        }
    """
    return {"new_cost_basis": None, "used_cost_basis": None}


def get_work_order_costs_mtd():
    """TODO once the work-order feature (Person 1 / reconditioning) exists:
        from catalog.models import WorkOrder
        return WorkOrder.objects.filter(opened_at__gte=<month_start>).aggregate(...)
    """
    return None


def get_vehicle_cost_basis(vehicle_id):
    """TODO once catalog app exists:
        from catalog.models import Vehicle
        v = Vehicle.objects.filter(pk=vehicle_id).first()
        return v.total_cost_basis if v else None
    """
    return None
