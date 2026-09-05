from copy import deepcopy
import re
from .forms import DealForm, VendorForm, PurchaseOrderStatusForm  
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from services import auth_service
from services.api_client import APIError, api_is_configured
from services.mock_data import current_user as preview_user
from services.presenters import ALLOWED_ROLES, normalize_role, unwrap, user_identity

from . import mock_data, presenters, service
from .forms import PurchaseOrderStatusForm, VehicleForm, VendorForm


PAGE_SIZE = 10
VALID_TABS = {"vehicles", "vendors", "purchase-orders"}
EDIT_ROLES = {"admin", "agent"}
PREVIEW_SESSION_KEYS = {
    "vehicles": "adms_preview_vehicles",
    "vendors": "adms_preview_vendors",
    "purchase-orders": "adms_preview_purchase_orders",
}


def _preview_mode():
    default = getattr(settings, "DASHBOARD_PREVIEW_MODE", not api_is_configured())
    return bool(getattr(settings, "ADMS_PREVIEW_MODE", default))


def _redirect_to_login(request, message=None):
    auth_service.clear_login(request)
    if message:
        messages.error(request, message)
    return redirect("login-page")


def _page_access(request):
    preview_mode = _preview_mode()
    try:
        if preview_mode:
            role = getattr(settings, "DASHBOARD_PREVIEW_ROLE", "admin")
            user = preview_user(role)
        else:
            user = auth_service.verified_user(request)
    except auth_service.AuthenticationRequired:
        return None, preview_mode, _redirect_to_login(
            request, "Please sign in to access inventory."
        )
    except APIError as error:
        return None, preview_mode, _redirect_to_login(request, error.message)

    role = normalize_role(user.get("role"))
    if role not in ALLOWED_ROLES:
        return None, preview_mode, _redirect_to_login(
            request, "Your account does not have inventory access."
        )
    return user, preview_mode, None


def _base_context(user, *, active_tab="vehicles"):
    role = normalize_role(user.get("role"))
    return {
        "active_page": "inventory",
        "active_tab": active_tab,
        "current_user": user,
        "user_identity": user_identity(user),
        "is_admin": role == "admin",
        "can_edit_inventory": role in EDIT_ROLES,
        "can_remove_inventory": role == "admin",
    }


def _preview_collection(request, tab):
    key = PREVIEW_SESSION_KEYS[tab]
    data = request.session.get(key)
    if not isinstance(data, list):
        factories = {
            "vehicles": mock_data.get_vehicles,
            "vendors": mock_data.get_vendors,
            "purchase-orders": mock_data.get_purchase_orders,
        }
        data = factories[tab]()
        request.session[key] = data
    return deepcopy(data)


def _save_preview_collection(request, tab, data):
    request.session[PREVIEW_SESSION_KEYS[tab]] = data
    request.session.modified = True


def _find_preview_item(request, tab, item_id):
    return next(
        (
            item
            for item in _preview_collection(request, tab)
            if str(item.get("id")) == str(item_id)
        ),
        None,
    )


def _next_preview_id(items, prefix, minimum):
    numbers = []
    for item in items:
        match = re.search(r"(\d+)$", str(item.get("id", "")))
        if match:
            numbers.append(int(match.group(1)))
    return f"{prefix}{max(numbers, default=minimum - 1) + 1}"


def _inventory_url(tab):
    return f"{reverse('inventory:inventory')}?tab={tab}"


def _add_api_errors(form, error):
    field_error_added = False
    for field_name, field_messages in error.field_errors.items():
        if field_name not in form.fields:
            continue
        if not isinstance(field_messages, (list, tuple)):
            field_messages = [field_messages]
        for field_message in field_messages:
            form.add_error(field_name, str(field_message))
            field_error_added = True
    if not field_error_added:
        form.add_error(None, error.message)


def _api_redirect_if_auth_error(request, error):
    if error.status_code == 401:
        return _redirect_to_login(
            request, "Your session expired. Please sign in again."
        )
    if error.status_code == 403:
        messages.error(request, "You do not have permission for that action.")
        return redirect("inventory:inventory")
    return None


def _filter_preview(items, tab, search, status):
    search_value = search.strip().lower()
    status_value = status.strip().upper()
    filtered = []
    for item in items:
        row_text = " ".join(str(value) for value in item.values()).lower()
        if search_value and search_value not in row_text:
            continue
        if tab == "vendors" and status:
            is_active = bool(item.get("is_active", True))
            if status.lower() == "active" and not is_active:
                continue
            if status.lower() == "inactive" and is_active:
                continue
        elif status_value and str(item.get("status", "")).upper() != status_value:
            continue
        filtered.append(item)
    return filtered


def _page_number(request):
    try:
        return max(1, int(request.GET.get("page", "1")))
    except (TypeError, ValueError):
        return 1


@require_GET
def inventory_page(request):
    user, preview_mode, response = _page_access(request)
    if response:
        return response

    active_tab = request.GET.get("tab", "vehicles")
    if active_tab not in VALID_TABS:
        active_tab = "vehicles"
    search = request.GET.get("search", "").strip()
    status = request.GET.get("status", "").strip()
    requested_page = _page_number(request)
    errors = []

    normalizers = {
        "vehicles": presenters.normalize_vehicle,
        "vendors": presenters.normalize_vendor,
        "purchase-orders": presenters.normalize_purchase_order,
    }

    if preview_mode:
        filtered = _filter_preview(
            _preview_collection(request, active_tab),
            active_tab,
            search,
            status,
        )
        paginator = Paginator(filtered, PAGE_SIZE)
        page_object = paginator.get_page(requested_page)
        rows = [normalizers[active_tab](item) for item in page_object.object_list]
        count = paginator.count
        current_page = page_object.number
        has_previous = page_object.has_previous()
        has_next = page_object.has_next()
    else:
        token = auth_service.access_token(request)
        try:
            if active_tab == "vehicles":
                payload = service.get_vehicles(
                    token,
                    search=search,
                    status=status,
                    page=requested_page,
                    page_size=PAGE_SIZE,
                )
            elif active_tab == "vendors":
                payload = service.get_vendors(
                    token,
                    search=search,
                    page=requested_page,
                    page_size=PAGE_SIZE,
                )
            else:
                payload = service.get_purchase_orders(
                    token,
                    status=status,
                    page=requested_page,
                    page_size=PAGE_SIZE,
                )
            rows, count, has_previous, has_next = presenters.page_results(
                payload,
                normalizers[active_tab],
                requested_page=requested_page,
                page_size=PAGE_SIZE,
            )
            if active_tab in {"vendors", "purchase-orders"} and (search or status):
                rows = _filter_preview(rows, active_tab, search, status)
            current_page = requested_page
        except APIError as error:
            auth_response = _api_redirect_if_auth_error(request, error)
            if auth_response:
                return auth_response
            errors.append(f"Could not load inventory: {error.message}")
            rows = []
            count = 0
            current_page = requested_page
            has_previous = requested_page > 1
            has_next = False

    context = _base_context(user, active_tab=active_tab)
    display_start = (current_page - 1) * PAGE_SIZE + 1 if count else 0
    display_end = min(current_page * PAGE_SIZE, count)
    context.update(
        {
            "rows": rows,
            "result_count": count,
            "search_query": search,
            "selected_status": status,
            "current_page": current_page,
            "previous_page": current_page - 1,
            "next_page": current_page + 1,
            "has_previous": has_previous,
            "has_next": has_next,
            "page_size": PAGE_SIZE,
            "display_start": display_start,
            "display_end": display_end,
            "inventory_errors": errors,
            "status_choices": mock_data.STATUS_CHOICES,
            "preview_mode": preview_mode,
        }
    )
    return render(request, "inventory/inventory.html", context)


def _require_edit_role(request, user, tab):
    if normalize_role(user.get("role")) in EDIT_ROLES:
        return None
    messages.error(request, "Only an Admin or Agent can modify inventory.")
    return HttpResponseRedirect(_inventory_url(tab))


def _form_context(user, form, *, title, description, tab, submit_label):
    context = _base_context(user, active_tab=tab)
    context.update(
        {
            "form": form,
            "form_title": title,
            "form_description": description,
            "submit_label": submit_label,
            "back_url": _inventory_url(tab),
        }
    )
    return context


@require_http_methods(["GET", "POST"])
def vehicle_add_page(request):
    user, preview_mode, response = _page_access(request)
    if response:
        return response
    denied = _require_edit_role(request, user, "vehicles")
    if denied:
        return denied

    form = VehicleForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        payload = form.api_payload()
        if preview_mode:
            vehicles = _preview_collection(request, "vehicles")
            preview_vehicle = {
                "id": _next_preview_id(vehicles, "V-", 1000),
                **payload,
                "purchase_order": payload.get("purchase_order_id") or "—",
            }
            preview_vehicle["cost_basis"] = sum(
                float(payload.get(name) or 0)
                for name in (
                    "acquisition_cost",
                    "transport_cost",
                    "recon_cost",
                )
            )
            vehicles.append(preview_vehicle)
            _save_preview_collection(request, "vehicles", vehicles)
            messages.success(request, "Vehicle added in preview mode.")
            return HttpResponseRedirect(_inventory_url("vehicles"))
        try:
            service.create_vehicle(auth_service.access_token(request), payload)
            messages.success(request, "Vehicle added successfully.")
            return HttpResponseRedirect(_inventory_url("vehicles"))
        except APIError as error:
            auth_response = _api_redirect_if_auth_error(request, error)
            if auth_response:
                return auth_response
            _add_api_errors(form, error)

    return render(
        request,
        "inventory/form.html",
        _form_context(
            user,
            form,
            title="Add Vehicle",
            description="Record a vehicle and its acquisition costs.",
            tab="vehicles",
            submit_label="Save Vehicle",
        ),
    )


def _vehicle_initial(vehicle):
    return {
        "vin": vehicle.get("vin", ""),
        "make": vehicle.get("make", ""),
        "model": vehicle.get("model", ""),
        "year": vehicle.get("year", ""),
        "trim": vehicle.get("trim", ""),
        "condition": vehicle.get("condition", "Used"),
        "purchase_order_id": vehicle.get("purchase_order_id")
        or vehicle.get("purchase_order")
        or "",
        "status": str(vehicle.get("status") or "AVAILABLE").upper(),
        "acquisition_cost": vehicle.get("acquisition_cost", 0),
        "transport_cost": vehicle.get("transport_cost", 0),
        "recon_cost": vehicle.get("recon_cost", 0),
    }


@require_http_methods(["GET", "POST"])
def vehicle_edit_page(request, vehicle_id):
    user, preview_mode, response = _page_access(request)
    if response:
        return response
    denied = _require_edit_role(request, user, "vehicles")
    if denied:
        return denied

    vehicle = None
    if request.method == "GET":
        if preview_mode:
            vehicle = _find_preview_item(request, "vehicles", vehicle_id)
        else:
            try:
                vehicle = unwrap(
                    service.get_vehicle(
                        auth_service.access_token(request), vehicle_id
                    )
                )
            except APIError as error:
                if error.status_code == 404:
                    raise Http404("Vehicle not found") from error
                auth_response = _api_redirect_if_auth_error(request, error)
                if auth_response:
                    return auth_response
                messages.error(request, error.message)
                return HttpResponseRedirect(_inventory_url("vehicles"))
        if not isinstance(vehicle, dict):
            raise Http404("Vehicle not found")

    form = VehicleForm(
        request.POST if request.method == "POST" else None,
        initial=_vehicle_initial(vehicle) if vehicle else None,
    )
    if request.method == "POST" and form.is_valid():
        payload = form.api_payload()
        if preview_mode:
            vehicles = _preview_collection(request, "vehicles")
            for index, item in enumerate(vehicles):
                if str(item.get("id")) == str(vehicle_id):
                    updated = {
                        **item,
                        **payload,
                        "purchase_order": payload.get("purchase_order_id") or "—",
                    }
                    updated["cost_basis"] = sum(
                        float(payload.get(name) or 0)
                        for name in (
                            "acquisition_cost",
                            "transport_cost",
                            "recon_cost",
                        )
                    )
                    vehicles[index] = updated
                    break
            else:
                raise Http404("Vehicle not found")
            _save_preview_collection(request, "vehicles", vehicles)
            messages.success(request, "Vehicle updated in preview mode.")
            return HttpResponseRedirect(_inventory_url("vehicles"))
        try:
            service.update_vehicle(
                auth_service.access_token(request), vehicle_id, payload
            )
            messages.success(request, "Vehicle updated successfully.")
            return HttpResponseRedirect(_inventory_url("vehicles"))
        except APIError as error:
            auth_response = _api_redirect_if_auth_error(request, error)
            if auth_response:
                return auth_response
            _add_api_errors(form, error)

    return render(
        request,
        "inventory/form.html",
        _form_context(
            user,
            form,
            title="Edit Vehicle",
            description=f"Update vehicle {vehicle_id}.",
            tab="vehicles",
            submit_label="Save Changes",
        ),
    )


def _load_detail(request, preview_mode, tab, item_id, api_call):
    if preview_mode:
        item = _find_preview_item(request, tab, item_id)
    else:
        item = unwrap(api_call(auth_service.access_token(request), item_id))
    if not isinstance(item, dict):
        raise Http404("Item not found")
    return item


@require_GET
def vehicle_detail_page(request, vehicle_id):
    user, preview_mode, response = _page_access(request)
    if response:
        return response
    try:
        vehicle = presenters.normalize_vehicle(
            _load_detail(
                request,
                preview_mode,
                "vehicles",
                vehicle_id,
                service.get_vehicle,
            )
        )
    except APIError as error:
        if error.status_code == 404:
            raise Http404("Vehicle not found") from error
        auth_response = _api_redirect_if_auth_error(request, error)
        if auth_response:
            return auth_response
        messages.error(request, error.message)
        return HttpResponseRedirect(_inventory_url("vehicles"))

    fields = [
        ("VIN", vehicle["vin"]),
        ("Vehicle", f"{vehicle['year']} {vehicle['make']} {vehicle['model']}"),
        ("Trim", vehicle["trim"] or "—"),
        ("Condition", vehicle["condition"]),
        ("Purchase Order", vehicle["purchase_order"]),
        ("Status", vehicle["status_label"]),
        ("Acquisition Cost", vehicle["acquisition_cost_display"]),
        ("Transport Cost", vehicle["transport_cost_display"]),
        ("Reconditioning Cost", vehicle["recon_cost_display"]),
        ("Total Cost Basis", vehicle["cost_basis_display"]),
    ]
    context = _base_context(user, active_tab="vehicles")
    context.update(
        {
            "detail_title": f"Vehicle {vehicle_id}",
            "detail_description": "Vehicle inventory details",
            "detail_fields": fields,
            "back_url": _inventory_url("vehicles"),
            "edit_url": reverse(
                "inventory:vehicle-edit", kwargs={"vehicle_id": vehicle_id}
            ),
        }
    )
    return render(request, "inventory/detail.html", context)


@require_http_methods(["GET", "POST"])
def vehicle_remove_page(request, vehicle_id):
    user, preview_mode, response = _page_access(request)
    if response:
        return response
    if normalize_role(user.get("role")) != "admin":
        messages.error(request, "Only an Admin can remove a vehicle.")
        return HttpResponseRedirect(_inventory_url("vehicles"))

    if preview_mode and not _find_preview_item(request, "vehicles", vehicle_id):
        raise Http404("Vehicle not found")

    if request.method == "POST":
        if preview_mode:
            vehicles = [
                item
                for item in _preview_collection(request, "vehicles")
                if str(item.get("id")) != str(vehicle_id)
            ]
            _save_preview_collection(request, "vehicles", vehicles)
            messages.success(request, "Vehicle removed in preview mode.")
            return HttpResponseRedirect(_inventory_url("vehicles"))
        try:
            service.delete_vehicle(auth_service.access_token(request), vehicle_id)
            messages.success(request, "Vehicle removed successfully.")
            return HttpResponseRedirect(_inventory_url("vehicles"))
        except APIError as error:
            auth_response = _api_redirect_if_auth_error(request, error)
            if auth_response:
                return auth_response
            messages.error(request, error.message)
            return HttpResponseRedirect(_inventory_url("vehicles"))

    context = _base_context(user, active_tab="vehicles")
    context.update(
        {
            "item_name": f"vehicle {vehicle_id}",
            "back_url": _inventory_url("vehicles"),
        }
    )
    return render(request, "inventory/confirm_remove.html", context)


@require_http_methods(["GET", "POST"])
def vendor_add_page(request):
    user, preview_mode, response = _page_access(request)
    if response:
        return response
    denied = _require_edit_role(request, user, "vendors")
    if denied:
        return denied

    form = VendorForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        payload = form.api_payload()
        if preview_mode:
            vendors = _preview_collection(request, "vendors")
            vendors.append(
                {
                    "id": _next_preview_id(vendors, "VD-", 100),
                    **payload,
                }
            )
            _save_preview_collection(request, "vendors", vendors)
            messages.success(request, "Vendor added in preview mode.")
            return HttpResponseRedirect(_inventory_url("vendors"))
        try:
            service.create_vendor(auth_service.access_token(request), payload)
            messages.success(request, "Vendor added successfully.")
            return HttpResponseRedirect(_inventory_url("vendors"))
        except APIError as error:
            auth_response = _api_redirect_if_auth_error(request, error)
            if auth_response:
                return auth_response
            _add_api_errors(form, error)

    return render(
        request,
        "inventory/form.html",
        _form_context(
            user,
            form,
            title="Add Vendor",
            description="Create a vendor for procurement operations.",
            tab="vendors",
            submit_label="Save Vendor",
        ),
    )


def _vendor_initial(vendor):
    return {
        "name": vendor.get("name", ""),
        "contact_name": vendor.get("contact_name", ""),
        "phone": vendor.get("phone", ""),
        "email": vendor.get("email", ""),
        "payment_terms": vendor.get("payment_terms", ""),
        "is_active": bool(vendor.get("is_active", True)),
    }


@require_http_methods(["GET", "POST"])
def vendor_edit_page(request, vendor_id):
    user, preview_mode, response = _page_access(request)
    if response:
        return response
    denied = _require_edit_role(request, user, "vendors")
    if denied:
        return denied

    vendor = None
    if request.method == "GET":
        if preview_mode:
            vendor = _find_preview_item(request, "vendors", vendor_id)
        else:
            try:
                vendor = unwrap(
                    service.get_vendor(auth_service.access_token(request), vendor_id)
                )
            except APIError as error:
                if error.status_code == 404:
                    raise Http404("Vendor not found") from error
                auth_response = _api_redirect_if_auth_error(request, error)
                if auth_response:
                    return auth_response
                messages.error(request, error.message)
                return HttpResponseRedirect(_inventory_url("vendors"))
        if not isinstance(vendor, dict):
            raise Http404("Vendor not found")

    form = VendorForm(
        request.POST if request.method == "POST" else None,
        initial=_vendor_initial(vendor) if vendor else None,
    )
    if request.method == "POST" and form.is_valid():
        payload = form.api_payload()
        if preview_mode:
            vendors = _preview_collection(request, "vendors")
            for index, item in enumerate(vendors):
                if str(item.get("id")) == str(vendor_id):
                    vendors[index] = {**item, **payload}
                    break
            else:
                raise Http404("Vendor not found")
            _save_preview_collection(request, "vendors", vendors)
            messages.success(request, "Vendor updated in preview mode.")
            return HttpResponseRedirect(_inventory_url("vendors"))
        try:
            service.update_vendor(
                auth_service.access_token(request), vendor_id, payload
            )
            messages.success(request, "Vendor updated successfully.")
            return HttpResponseRedirect(_inventory_url("vendors"))
        except APIError as error:
            auth_response = _api_redirect_if_auth_error(request, error)
            if auth_response:
                return auth_response
            _add_api_errors(form, error)

    return render(
        request,
        "inventory/form.html",
        _form_context(
            user,
            form,
            title="Edit Vendor",
            description=f"Update vendor {vendor_id}.",
            tab="vendors",
            submit_label="Save Changes",
        ),
    )


@require_GET
def vendor_detail_page(request, vendor_id):
    user, preview_mode, response = _page_access(request)
    if response:
        return response
    try:
        vendor = presenters.normalize_vendor(
            _load_detail(
                request,
                preview_mode,
                "vendors",
                vendor_id,
                service.get_vendor,
            )
        )
    except APIError as error:
        if error.status_code == 404:
            raise Http404("Vendor not found") from error
        auth_response = _api_redirect_if_auth_error(request, error)
        if auth_response:
            return auth_response
        messages.error(request, error.message)
        return HttpResponseRedirect(_inventory_url("vendors"))

    fields = [
        ("Vendor Name", vendor["name"]),
        ("Contact", vendor["contact_name"]),
        ("Phone", vendor["phone"]),
        ("Email", vendor["email"]),
        ("Payment Terms", vendor["payment_terms"]),
        ("Status", vendor["status_label"]),
    ]
    context = _base_context(user, active_tab="vendors")
    context.update(
        {
            "detail_title": f"Vendor {vendor_id}",
            "detail_description": "Vendor procurement details",
            "detail_fields": fields,
            "back_url": _inventory_url("vendors"),
            "edit_url": reverse(
                "inventory:vendor-edit", kwargs={"vendor_id": vendor_id}
            ),
        }
    )
    return render(request, "inventory/detail.html", context)


@require_GET
def purchase_order_detail_page(request, purchase_order_id):
    user, preview_mode, response = _page_access(request)
    if response:
        return response
    try:
        purchase_order = presenters.normalize_purchase_order(
            _load_detail(
                request,
                preview_mode,
                "purchase-orders",
                purchase_order_id,
                service.get_purchase_order,
            )
        )
    except APIError as error:
        if error.status_code == 404:
            raise Http404("Purchase order not found") from error
        auth_response = _api_redirect_if_auth_error(request, error)
        if auth_response:
            return auth_response
        messages.error(request, error.message)
        return HttpResponseRedirect(_inventory_url("purchase-orders"))

    fields = [
        ("PO Number", purchase_order["id"]),
        ("Vendor", purchase_order["vendor"]),
        ("Order Date", purchase_order["order_date"]),
        ("Expected Date", purchase_order["expected_date"]),
        ("Status", purchase_order["status_label"]),
    ]
    context = _base_context(user, active_tab="purchase-orders")
    context.update(
        {
            "detail_title": f"Purchase Order {purchase_order_id}",
            "detail_description": "Purchase-order details",
            "detail_fields": fields,
            "back_url": _inventory_url("purchase-orders"),
            "edit_url": "",
        }
    )
    return render(request, "inventory/detail.html", context)


@require_POST
def purchase_order_status_page(request, purchase_order_id):
    user, preview_mode, response = _page_access(request)
    if response:
        return response
    denied = _require_edit_role(request, user, "purchase-orders")
    if denied:
        return denied

    form = PurchaseOrderStatusForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Select a valid purchase-order status.")
        return HttpResponseRedirect(_inventory_url("purchase-orders"))
    new_status = form.cleaned_data["status"]

    if preview_mode:
        purchase_orders = _preview_collection(request, "purchase-orders")
        for index, item in enumerate(purchase_orders):
            if str(item.get("id")) == str(purchase_order_id):
                purchase_orders[index] = {
                    **item,
                    "status": new_status,
                    "status_label": presenters.status_label(new_status),
                    "status_style": presenters.status_style(new_status),
                }
                break
        else:
            raise Http404("Purchase order not found")
        _save_preview_collection(request, "purchase-orders", purchase_orders)
        messages.success(request, "Purchase-order status updated in preview mode.")
        return HttpResponseRedirect(_inventory_url("purchase-orders"))

    try:
        service.update_purchase_order_status(
            auth_service.access_token(request), purchase_order_id, new_status
        )
        messages.success(request, "Purchase-order status updated successfully.")
    except APIError as error:
        auth_response = _api_redirect_if_auth_error(request, error)
        if auth_response:
            return auth_response
        messages.error(request, error.message)
    return HttpResponseRedirect(_inventory_url("purchase-orders"))


@require_http_methods(["GET", "POST"])
def deal_add_page(request):
    user, preview_mode, response = _page_access(request)
    if response:
        return response
    denied = _require_edit_role(request, user, "deals")
    if denied:
        return denied

    form = DealForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        payload = form.api_payload()
        if preview_mode:
            deals = _preview_collection(request, "deals")
            deals.append(
                {
                    "id": _next_preview_id(deals, "DL-", 100),
                    **payload,
                }
            )
            _save_preview_collection(request, "deals", deals)
            messages.success(request, "Deal created in preview mode.")
            return HttpResponseRedirect(_inventory_url("deals"))
        try:
            service.create_deal(auth_service.access_token(request), payload)
            messages.success(request, "Deal created successfully.")
            return HttpResponseRedirect(_inventory_url("deals"))
        except APIError as error:
            auth_response = _api_redirect_if_auth_error(request, error)
            if auth_response:
                return auth_response
            _add_api_errors(form, error)

    return render(
        request,
        "sales/create_deal.html",
        _form_context(
            user,
            form,
            title="Create New Deal",
            description="Complete the steps below to finalize the sale and optional trade-in.",
            tab="deals",
            submit_label="Finalize Deal",
        ),
    )


def _deal_initial(deal):
    return {
        "customer_id": deal.get("customer_id", ""),
        "vehicle_id": deal.get("vehicle_id", ""),
        "discount": deal.get("discount", ""),
        "trade_in_enabled": bool(deal.get("trade_in_enabled", False)),
        "trade_in_vehicle_id": deal.get("trade_in_vehicle_id", ""),
        "appraised_value": deal.get("appraised_value", ""),
    }


@require_http_methods(["GET", "POST"])
def deal_edit_page(request, deal_id):
    user, preview_mode, response = _page_access(request)
    if response:
        return response
    denied = _require_edit_role(request, user, "deals")
    if denied:
        return denied

    deal = None
    if request.method == "GET":
        if preview_mode:
            deal = _find_preview_item(request, "deals", deal_id)
        else:
            try:
                deal = unwrap(
                    service.get_deal(auth_service.access_token(request), deal_id)
                )
            except APIError as error:
                if error.status_code == 404:
                    raise Http404("Deal not found") from error
                auth_response = _api_redirect_if_auth_error(request, error)
                if auth_response:
                    return auth_response
                messages.error(request, error.message)
                return HttpResponseRedirect(_inventory_url("deals"))
        if not isinstance(deal, dict):
            raise Http404("Deal not found")

    form = DealForm(
        request.POST if request.method == "POST" else None,
        initial=_deal_initial(deal) if deal else None,
    )
    if request.method == "POST" and form.is_valid():
        payload = form.api_payload()
        if preview_mode:
            deals = _preview_collection(request, "deals")
            for index, item in enumerate(deals):
                if str(item.get("id")) == str(deal_id):
                    deals[index] = {**item, **payload}
                    break
            else:
                raise Http404("Deal not found")
            _save_preview_collection(request, "deals", deals)
            messages.success(request, "Deal updated in preview mode.")
            return HttpResponseRedirect(_inventory_url("deals"))
        try:
            service.update_deal(
                auth_service.access_token(request), deal_id, payload
            )
            messages.success(request, "Deal updated successfully.")
            return HttpResponseRedirect(_inventory_url("deals"))
        except APIError as error:
            auth_response = _api_redirect_if_auth_error(request, error)
            if auth_response:
                return auth_response
            _add_api_errors(form, error)

    return render(
        request,
        "sales/create_deal.html",
        _form_context(
            user,
            form,
            title="Edit Deal",
            description=f"Update deal {deal_id}.",
            tab="deals",
            submit_label="Save Changes",
        ),
    )


@require_GET
def deal_detail_page(request, deal_id):
    user, preview_mode, response = _page_access(request)
    if response:
        return response
    try:
        deal = presenters.normalize_deal(
            _load_detail(
                request,
                preview_mode,
                "deals",
                deal_id,
                service.get_deal,
            )
        )
    except APIError as error:
        if error.status_code == 404:
            raise Http404("Deal not found") from error
        auth_response = _api_redirect_if_auth_error(request, error)
        if auth_response:
            return auth_response
        messages.error(request, error.message)
        return HttpResponseRedirect(_inventory_url("deals"))

    fields = [
        ("Customer", deal.get("customer", "—")),
        ("Vehicle", deal.get("vehicle", "—")),
        ("Base Price", deal.get("base_price_display", "—")),
        ("Discount", deal.get("discount_display", "—")),
        ("Taxes & Fees", deal.get("taxes_display", "—")),
        ("Trade-In Status", "Applied" if deal.get("trade_in_enabled") else "None"),
        ("Balance Due", deal.get("balance_due_display", "—")),
        ("Sales Agent", deal.get("sales_agent", "—")),
    ]
    context = _base_context(user, active_tab="deals")
    context.update(
        {
            "detail_title": f"Deal {deal_id}",
            "detail_description": "Sales & trade-in finalized deal summary",
            "detail_fields": fields,
            "back_url": _inventory_url("deals"),
            "edit_url": reverse(
                "inventory:deal-edit", kwargs={"deal_id": deal_id}
            ),
        }
    )
    return render(request, "inventory/detail.html", context)



def deal_invoice_view(request, deal_id):
    return render(request, 'sales/invoice.html', {'deal_id': deal_id})