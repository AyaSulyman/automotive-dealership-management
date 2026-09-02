from django.shortcuts import render

from . import mock_data


def inventory_page(request):
    """
    Inventory & Procurement page: Vehicles / Vendors / Purchase Orders tabs.

    All data below is mocked (see mock_data.py) because the backend/API is
    not built yet. Swap each mock_data.get_*() call for a real queryset once
    the `vehicle`, `vendor` and `purchase_order` models exist -- the
    templates read from the same context keys either way.
    """
    context = {
        'active_tab': request.GET.get('tab', 'vehicles'),
        'vehicles': mock_data.get_vehicles(),
        'vendors': mock_data.get_vendors(),
        'purchase_orders': mock_data.get_purchase_orders(),
        'status_choices': mock_data.STATUS_CHOICES,
        'condition_choices': mock_data.CONDITION_CHOICES,
    }
    return render(request, 'inventory/inventory.html', context)
