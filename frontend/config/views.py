from copy import deepcopy

from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import EmployeeForm, LoginForm
from services import auth_service, dashboard_service, mock_data
from services.api_client import APIError, api_is_configured
from services.presenters import (
    ALLOWED_ROLES,
    employee_rows,
    filter_rows,
    invoice_rows,
    normalize_role,
    overview_context,
    payment_rows,
    unwrap,
    user_identity,
)


PREVIEW_EMPLOYEES_SESSION_KEY = "adms_preview_employees"


def _preview_mode():
    return bool(
        getattr(settings, "DASHBOARD_PREVIEW_MODE", not api_is_configured())
    )


def _add_api_errors(form, error):
    applied_field_error = False
    for field_name, field_messages in error.field_errors.items():
        if field_name not in form.fields:
            continue
        if not isinstance(field_messages, (list, tuple)):
            field_messages = [field_messages]
        for field_message in field_messages:
            form.add_error(field_name, str(field_message))
            applied_field_error = True
    if not applied_field_error:
        form.add_error(None, error.message)


def _redirect_to_login(request, message=None):
    auth_service.clear_login(request)
    if message:
        messages.error(request, message)
    return redirect("login-page")


def _current_employee(request, preview_mode):
    if preview_mode:
        preview_role = getattr(settings, "DASHBOARD_PREVIEW_ROLE", "admin")
        return mock_data.current_user(preview_role)
    return auth_service.verified_user(request)


def _preview_employees(request):
    employees = request.session.get(PREVIEW_EMPLOYEES_SESSION_KEY)
    if not isinstance(employees, list):
        employees = mock_data.initial_employees()
        request.session[PREVIEW_EMPLOYEES_SESSION_KEY] = employees
    return deepcopy(employees)


def _save_preview_employees(request, employees):
    request.session[PREVIEW_EMPLOYEES_SESSION_KEY] = employees
    request.session.modified = True


def _employee_page_context(user, form, *, mode, employee_id=None):
    return {
        "active_page": "dashboard",
        "current_user": user,
        "user_identity": user_identity(user),
        "form": form,
        "form_mode": mode,
        "employee_id": employee_id,
        "is_admin": True,
    }


@require_http_methods(["GET", "POST"])
def login_page(request):
    if request.method == "GET" and request.session.get(
        auth_service.ACCESS_TOKEN_SESSION_KEY
    ):
        return redirect("dashboard")

    form = LoginForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            payload = auth_service.login(
                form.cleaned_data["email"],
                form.cleaned_data["password"],
            )
            auth_service.store_login(
                request,
                payload,
                remember=form.cleaned_data["remember_me"],
            )
            return redirect(
                getattr(settings, "LOGIN_SUCCESS_URL", reverse("dashboard"))
            )
        except APIError as error:
            _add_api_errors(form, error)

    return render(request, "login.html", {"form": form})


@require_http_methods(["GET"])
def dashboard_page(request):
    preview_mode = _preview_mode()
    try:
        user = _current_employee(request, preview_mode)
    except auth_service.AuthenticationRequired:
        return _redirect_to_login(request, "Please sign in to access the dashboard.")
    except APIError as error:
        return _redirect_to_login(request, error.message)

    role = normalize_role(user.get("role"))
    if role not in ALLOWED_ROLES:
        return _redirect_to_login(
            request, "Your account does not have dashboard access."
        )

    employee_search = request.GET.get("employee_search", "").strip()
    dashboard_errors = []

    if preview_mode:
        overview_payload = mock_data.overview()
        invoices_payload = mock_data.invoices()
        payments_payload = mock_data.payments()
        employees_payload = _preview_employees(request) if role == "admin" else []
    else:
        token = auth_service.access_token(request)
        overview_payload = {}
        invoices_payload = []
        payments_payload = []
        employees_payload = []

        calls = (
            ("overview", lambda: dashboard_service.get_overview(token)),
            (
                "recent invoices",
                lambda: dashboard_service.get_recent_invoices(token, limit=5),
            ),
            (
                "recent payments",
                lambda: dashboard_service.get_recent_payments(token, limit=5),
            ),
        )
        loaded = {}
        for label, call in calls:
            try:
                loaded[label] = call()
            except APIError as error:
                if error.status_code == 401:
                    return _redirect_to_login(
                        request, "Your session expired. Please sign in again."
                    )
                dashboard_errors.append(f"Could not load {label}: {error.message}")

        overview_payload = loaded.get("overview", {})
        invoices_payload = loaded.get("recent invoices", [])
        payments_payload = loaded.get("recent payments", [])

        if role == "admin":
            try:
                employees_payload = dashboard_service.get_employees(
                    token, search=employee_search
                )
            except APIError as error:
                if error.status_code == 401:
                    return _redirect_to_login(
                        request, "Your session expired. Please sign in again."
                    )
                if error.status_code == 403:
                    role = ""
                else:
                    dashboard_errors.append(
                        f"Could not load employees: {error.message}"
                    )

    invoices = invoice_rows(invoices_payload)
    payments = payment_rows(payments_payload)
    employees = employee_rows(employees_payload)

    if preview_mode and employee_search:
        employees = filter_rows(employees, employee_search)

    context = {
        "active_page": "dashboard",
        "current_user": user,
        "user_identity": user_identity(user),
        "is_admin": role == "admin",
        "overview": overview_context(overview_payload),
        "recent_invoices": invoices,
        "recent_payments": payments,
        "employees": employees,
        "employee_search": employee_search,
        "dashboard_errors": dashboard_errors,
        "preview_mode": preview_mode,
        "current_year": timezone.now().year,
    }
    return render(request, "dashboard/dashboard.html", context)


def _admin_request(request):
    preview_mode = _preview_mode()
    user = _current_employee(request, preview_mode)
    return user, preview_mode, normalize_role(user.get("role")) == "admin"


@require_http_methods(["GET", "POST"])
def employee_add_page(request):
    try:
        user, preview_mode, is_admin = _admin_request(request)
    except auth_service.AuthenticationRequired:
        return _redirect_to_login(request, "Please sign in to continue.")
    except APIError as error:
        return _redirect_to_login(request, error.message)

    if not is_admin:
        messages.error(request, "Only an Admin can manage employees.")
        return redirect("dashboard")

    form = EmployeeForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        if preview_mode:
            employees = _preview_employees(request)
            next_id = max((int(item.get("id", 0)) for item in employees), default=0) + 1
            employee = {"id": next_id, **form.api_payload()}
            employee.pop("password", None)
            employees.append(employee)
            _save_preview_employees(request, employees)
            messages.success(request, "Employee added in preview mode.")
            return HttpResponseRedirect(
                f"{reverse('dashboard')}#employee-management"
            )

        try:
            dashboard_service.create_employee(
                auth_service.access_token(request), form.api_payload()
            )
            messages.success(request, "Employee added successfully.")
            return HttpResponseRedirect(
                f"{reverse('dashboard')}#employee-management"
            )
        except APIError as error:
            if error.status_code == 401:
                return _redirect_to_login(
                    request, "Your session expired. Please sign in again."
                )
            if error.status_code == 403:
                messages.error(request, "Only an Admin can manage employees.")
                return redirect("dashboard")
            _add_api_errors(form, error)

    return render(
        request,
        "dashboard/employee_form.html",
        _employee_page_context(user, form, mode="add"),
    )


@require_http_methods(["GET", "POST"])
def employee_edit_page(request, employee_id):
    try:
        user, preview_mode, is_admin = _admin_request(request)
    except auth_service.AuthenticationRequired:
        return _redirect_to_login(request, "Please sign in to continue.")
    except APIError as error:
        return _redirect_to_login(request, error.message)

    if not is_admin:
        messages.error(request, "Only an Admin can manage employees.")
        return redirect("dashboard")

    employee = None
    if preview_mode:
        employee = next(
            (
                item
                for item in _preview_employees(request)
                if str(item.get("id")) == str(employee_id)
            ),
            None,
        )
    elif request.method == "GET":
        try:
            employee_payload = dashboard_service.get_employee(
                auth_service.access_token(request), employee_id
            )
            employee = unwrap(employee_payload)
        except APIError as error:
            if error.status_code == 404:
                raise Http404("Employee not found") from error
            if error.status_code == 401:
                return _redirect_to_login(
                    request, "Your session expired. Please sign in again."
                )
            messages.error(request, error.message)
            return redirect("dashboard")

    if request.method == "GET" and not isinstance(employee, dict):
        raise Http404("Employee not found")

    initial = None
    if employee:
        initial = {
            "name": employee.get("name")
            or employee.get("full_name")
            or "",
            "email": employee.get("email", ""),
            "role": normalize_role(employee.get("role")),
        }
    form = EmployeeForm(
        request.POST if request.method == "POST" else None,
        initial=initial,
        editing=True,
    )

    if request.method == "POST" and form.is_valid():
        if preview_mode:
            employees = _preview_employees(request)
            for index, item in enumerate(employees):
                if str(item.get("id")) == str(employee_id):
                    updated = {**item, **form.api_payload()}
                    updated.pop("password", None)
                    employees[index] = updated
                    break
            else:
                raise Http404("Employee not found")
            _save_preview_employees(request, employees)
            messages.success(request, "Employee updated in preview mode.")
            return HttpResponseRedirect(
                f"{reverse('dashboard')}#employee-management"
            )

        try:
            dashboard_service.update_employee(
                auth_service.access_token(request),
                employee_id,
                form.api_payload(),
            )
            messages.success(request, "Employee updated successfully.")
            return HttpResponseRedirect(
                f"{reverse('dashboard')}#employee-management"
            )
        except APIError as error:
            if error.status_code == 401:
                return _redirect_to_login(
                    request, "Your session expired. Please sign in again."
                )
            if error.status_code == 403:
                messages.error(request, "Only an Admin can manage employees.")
                return redirect("dashboard")
            _add_api_errors(form, error)

    return render(
        request,
        "dashboard/employee_form.html",
        _employee_page_context(
            user,
            form,
            mode="edit",
            employee_id=employee_id,
        ),
    )
