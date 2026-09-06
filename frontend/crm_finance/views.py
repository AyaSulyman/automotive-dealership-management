import csv
from copy import deepcopy
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from services import auth_service
from services.api_client import APIError, api_is_configured
from services.mock_data import current_user as preview_user
from services.presenters import ALLOWED_ROLES, list_results, normalize_role, unwrap, user_identity

from . import mock_data, presenters, services
from .forms import CustomerForm, PaymentForm


PAGE_SIZE = 10
CUSTOMER_EDIT_ROLES = {"admin", "agent"}
FINANCE_ROLES = {"admin", "accountant"}
PAYMENT_CREATE_ROLES = FINANCE_ROLES
VALID_PAYMENT_TABS = {"payments", "schedules", "financing"}
VALID_REPORT_TABS = {"overview", "vehicle-summary"}
SESSION_KEYS = {
    "customers": "adms_preview_customers",
    "invoices": "adms_preview_sales_invoices",
    "payments": "adms_preview_payments",
}


def _preview_mode():
    default = getattr(settings, "DASHBOARD_PREVIEW_MODE", not api_is_configured())
    return bool(getattr(settings, "ADMS_PREVIEW_MODE", default))


def _redirect_to_login(request, message=None):
    auth_service.clear_login(request)
    if message:
        messages.error(request, message)
    return redirect("login-page")


def _page_access(request, *, allowed_roles=CUSTOMER_EDIT_ROLES, label="this page"):
    preview_mode = _preview_mode()
    try:
        if preview_mode:
            role = getattr(settings, "DASHBOARD_PREVIEW_ROLE", "admin")
            user = preview_user(role)
        else:
            user = auth_service.verified_user(request)
    except auth_service.AuthenticationRequired:
        return None, preview_mode, _redirect_to_login(
            request, f"Please sign in to access {label}."
        )
    except APIError as error:
        return None, preview_mode, _redirect_to_login(request, error.message)

    role = normalize_role(user.get("role"))
    if role not in allowed_roles:
        from services.access import denied
        return None, preview_mode, denied(request, user)
    return user, preview_mode, None


def _base_context(user, active_page):
    role = normalize_role(user.get("role"))
    return {
        "active_page": active_page,
        "current_user": user,
        "user_identity": user_identity(user),
        "is_admin": role == "admin",
        "can_edit_customers": role in CUSTOMER_EDIT_ROLES,
        "can_record_payment": role in PAYMENT_CREATE_ROLES,
        "can_view_finance": role in FINANCE_ROLES,
    }


def _session_collection(request, name):
    data = request.session.get(SESSION_KEYS[name])
    if not isinstance(data, list):
        factories = {
            "customers": mock_data.customers,
            "invoices": mock_data.invoices,
            "payments": mock_data.payments,
        }
        data = factories[name]()
        request.session[SESSION_KEYS[name]] = data
    return deepcopy(data)


def _save_session_collection(request, name, data):
    request.session[SESSION_KEYS[name]] = data
    request.session.modified = True


def _find_item(items, item_id):
    return next(
        (
            item
            for item in items
            if str(item.get("id")) == str(item_id)
        ),
        None,
    )


def _next_numeric_id(items, minimum):
    values = []
    for item in items:
        try:
            values.append(int(item.get("id")))
        except (TypeError, ValueError):
            continue
    return max(values, default=minimum - 1) + 1


def _add_api_errors(form, error):
    added = False
    field_aliases = {
        "first_name": "full_name",
        "last_name": "full_name",
        "invoice": "invoice_id",
    }
    for field_name, field_messages in error.field_errors.items():
        field_name = field_aliases.get(field_name, field_name)
        if field_name not in form.fields:
            continue
        if not isinstance(field_messages, (list, tuple)):
            field_messages = [field_messages]
        for field_message in field_messages:
            form.add_error(field_name, str(field_message))
            added = True
    if not added:
        form.add_error(None, error.message)


def _api_error_response(request, error, fallback_name):
    if error.status_code == 401:
        return _redirect_to_login(
            request, "Your session expired. Please sign in again."
        )
    if error.status_code == 403:
        messages.error(request, "You do not have permission for that action.")
        return redirect(fallback_name)
    return None


def _page_number(request):
    try:
        return max(1, int(request.GET.get("page", "1")))
    except (TypeError, ValueError):
        return 1


def _customer_initial(customer):
    combined_name = " ".join(
        str(customer.get(part) or "").strip()
        for part in ("first_name", "last_name")
    ).strip()
    return {
        "full_name": combined_name
        or customer.get("full_name")
        or customer.get("name")
        or "",
        "id_type": customer.get("id_type") or "",
        "id_number": customer.get("id_number") or "",
        "phone": customer.get("phone") or "",
        "email": customer.get("email") or "",
        "address": customer.get("address") or "",
        "status": customer.get("status") or "ACTIVE",
    }


@require_GET
def customers_page(request):
    user, preview_mode, response = _page_access(
        request, label="customer records"
    )
    if response:
        return response

    search = request.GET.get("search", "").strip()
    customer_status = request.GET.get("status", "").strip().upper()
    requested_page = _page_number(request)
    errors = []

    if preview_mode:
        customers = _session_collection(request, "customers")
        if search:
            normalized = search.lower()
            customers = [
                customer
                for customer in customers
                if normalized
                in " ".join(str(value) for value in customer.values()).lower()
            ]
        if customer_status:
            customers = [
                customer
                for customer in customers
                if str(customer.get("status") or "ACTIVE").upper()
                == customer_status
            ]
        paginator = Paginator(customers, PAGE_SIZE)
        page_object = paginator.get_page(requested_page)
        rows = [
            presenters.customer_row(item) for item in page_object.object_list
        ]
        count = paginator.count
        current_page = page_object.number
        has_previous = page_object.has_previous()
        has_next = page_object.has_next()
    else:
        try:
            payload = services.get_customers(
                auth_service.access_token(request),
                search=search,
                status=customer_status,
                page=requested_page,
                page_size=PAGE_SIZE,
            )
            rows = presenters.customer_rows(payload)
            data = unwrap(payload)
            count = (
                int(data.get("count", len(rows)))
                if isinstance(data, dict)
                else len(rows)
            )
            current_page = requested_page
            has_previous = bool(
                data.get("previous") if isinstance(data, dict) else requested_page > 1
            )
            has_next = bool(
                data.get("next") if isinstance(data, dict) else False
            )
        except APIError as error:
            auth_response = _api_error_response(
                request, error, "crm_finance:customers"
            )
            if auth_response:
                return auth_response
            errors.append(f"Could not load customers: {error.message}")
            rows = []
            count = 0
            current_page = requested_page
            has_previous = False
            has_next = False

    context = _base_context(user, "customers")
    context.update(
        {
            "customers": rows,
            "search_query": search,
            "selected_status": customer_status,
            "customer_errors": errors,
            "result_count": count,
            "display_start": (current_page - 1) * PAGE_SIZE + 1 if count else 0,
            "display_end": min(current_page * PAGE_SIZE, count),
            "current_page": current_page,
            "previous_page": current_page - 1,
            "next_page": current_page + 1,
            "has_previous": has_previous,
            "has_next": has_next,
            "preview_mode": preview_mode,
        }
    )
    return render(request, "customers/customers.html", context)


def _customer_form_context(user, form, *, mode, customer_id=None):
    context = _base_context(user, "customers")
    context.update(
        {
            "form": form,
            "form_mode": mode,
            "customer_id": customer_id,
        }
    )
    return context


@require_http_methods(["GET", "POST"])
def customer_add_page(request):
    user, preview_mode, response = _page_access(
        request, allowed_roles=CUSTOMER_EDIT_ROLES, label="customer management"
    )
    if response:
        return response

    form = CustomerForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        payload = form.api_payload()
        if preview_mode:
            customers = _session_collection(request, "customers")
            customer_id = _next_numeric_id(customers, 89234)
            customers.append(
                {
                    "id": customer_id,
                    "customer_number": f"CUS-{customer_id}",
                    **payload,
                    "created_at": datetime.now().date().isoformat(),
                }
            )
            _save_session_collection(request, "customers", customers)
            messages.success(request, "Customer added in preview mode.")
            return redirect("crm_finance:customer-detail", customer_id=customer_id)
        try:
            result = services.create_customer(
                auth_service.access_token(request), payload
            )
            customer = unwrap(result)
            customer_id = customer.get("id") if isinstance(customer, dict) else None
            messages.success(request, "Customer added successfully.")
            if customer_id:
                return redirect(
                    "crm_finance:customer-detail", customer_id=customer_id
                )
            return redirect("crm_finance:customers")
        except APIError as error:
            auth_response = _api_error_response(
                request, error, "crm_finance:customers"
            )
            if auth_response:
                return auth_response
            _add_api_errors(form, error)

    return render(
        request,
        "customers/customer_form.html",
        _customer_form_context(user, form, mode="add"),
    )


@require_http_methods(["GET", "POST"])
def customer_edit_page(request, customer_id):
    user, preview_mode, response = _page_access(
        request, allowed_roles=CUSTOMER_EDIT_ROLES, label="customer management"
    )
    if response:
        return response

    if preview_mode:
        customers = _session_collection(request, "customers")
        customer = _find_item(customers, customer_id)
    else:
        try:
            customer = unwrap(
                services.get_customer(
                    auth_service.access_token(request), customer_id
                )
            )
        except APIError as error:
            if error.status_code == 404:
                raise Http404("Customer not found") from error
            auth_response = _api_error_response(
                request, error, "crm_finance:customers"
            )
            if auth_response:
                return auth_response
            messages.error(request, error.message)
            return redirect("crm_finance:customers")

    if not isinstance(customer, dict):
        raise Http404("Customer not found")

    form = CustomerForm(
        request.POST if request.method == "POST" else None,
        initial=_customer_initial(customer),
    )
    if request.method == "POST" and form.is_valid():
        payload = form.api_payload()
        if preview_mode:
            for index, item in enumerate(customers):
                if str(item.get("id")) == str(customer_id):
                    customers[index] = {**item, **payload}
                    break
            _save_session_collection(request, "customers", customers)
            messages.success(request, "Customer updated in preview mode.")
            return redirect(
                "crm_finance:customer-detail", customer_id=customer_id
            )
        try:
            services.update_customer(
                auth_service.access_token(request), customer_id, payload
            )
            messages.success(request, "Customer updated successfully.")
            return redirect(
                "crm_finance:customer-detail", customer_id=customer_id
            )
        except APIError as error:
            auth_response = _api_error_response(
                request, error, "crm_finance:customers"
            )
            if auth_response:
                return auth_response
            _add_api_errors(form, error)

    return render(
        request,
        "customers/customer_form.html",
        _customer_form_context(
            user, form, mode="edit", customer_id=customer_id
        ),
    )


@require_GET
def customer_detail_page(request, customer_id):
    user, preview_mode, response = _page_access(
        request, label="customer records"
    )
    if response:
        return response
    errors = []

    if preview_mode:
        customer = _find_item(
            _session_collection(request, "customers"), customer_id
        )
        history_payload = mock_data.customer_history(customer_id)
    else:
        token = auth_service.access_token(request)
        try:
            customer = unwrap(services.get_customer(token, customer_id))
        except APIError as error:
            if error.status_code == 404:
                raise Http404("Customer not found") from error
            auth_response = _api_error_response(
                request, error, "crm_finance:customers"
            )
            if auth_response:
                return auth_response
            messages.error(request, error.message)
            return redirect("crm_finance:customers")
        try:
            history_payload = services.get_customer_history(token, customer_id)
        except APIError as error:
            history_payload = []
            errors.append(f"Could not load customer history: {error.message}")

    if not isinstance(customer, dict):
        raise Http404("Customer not found")

    context = _base_context(user, "customers")
    context.update(
        {
            "customer": presenters.customer_row(customer),
            "history": presenters.history_rows(history_payload),
            "customer_errors": errors,
        }
    )
    return render(request, "customers/customer_detail.html", context)


def _filter_payments(items, invoice_id, method, date_from, date_to):
    filtered = []
    for item in items:
        if invoice_id and str(item.get("invoice_id")) != str(invoice_id):
            continue
        if method and str(item.get("method", "")).upper() != method.upper():
            continue
        paid_at = str(item.get("paid_at") or "")[:10]
        if date_from and paid_at < date_from:
            continue
        if date_to and paid_at > date_to:
            continue
        filtered.append(item)
    return filtered


@require_GET
def payments_page(request):
    user, preview_mode, response = _page_access(
        request, allowed_roles=FINANCE_ROLES, label="payments and financing"
    )
    if response:
        return response

    active_tab = request.GET.get("tab", "payments")
    if active_tab not in VALID_PAYMENT_TABS:
        active_tab = "payments"
    invoice_id = request.GET.get("invoice_id", "").strip()
    method = request.GET.get("method", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    errors = []

    if preview_mode:
        if active_tab == "payments":
            payload = _filter_payments(
                _session_collection(request, "payments"),
                invoice_id,
                method,
                date_from,
                date_to,
            )
            rows = presenters.payment_rows(payload)
        elif active_tab == "schedules":
            payload = mock_data.schedules()
            if invoice_id:
                payload = [
                    item
                    for item in payload
                    if str(item.get("invoice_id")) == invoice_id
                ]
            rows = presenters.schedule_rows(payload)
        else:
            payload = mock_data.financing_accounts()
            if invoice_id:
                payload = [
                    item
                    for item in payload
                    if str(item.get("invoice_id")) == invoice_id
                ]
            rows = presenters.financing_rows(payload)
        invoice_options = presenters.invoice_rows(
            _session_collection(request, "invoices")
        )
    else:
        token = auth_service.access_token(request)
        try:
            if active_tab == "payments":
                payload = services.get_payments(
                    token,
                    invoice_id=invoice_id,
                    method=method,
                    date_from=date_from,
                    date_to=date_to,
                )
                rows = presenters.payment_rows(payload)
            elif active_tab == "schedules":
                rows = presenters.schedule_rows(
                    services.get_payment_schedules(
                        token, invoice_id=invoice_id
                    )
                )
            else:
                rows = presenters.financing_rows(
                    services.get_financing_accounts(
                        token, invoice_id=invoice_id
                    )
                )
        except APIError as error:
            auth_response = _api_error_response(
                request, error, "crm_finance:payments"
            )
            if auth_response:
                return auth_response
            errors.append(f"Could not load this section: {error.message}")
            rows = []
        try:
            invoice_options = presenters.invoice_rows(
                services.get_sales_invoices(token)
            )
        except APIError:
            invoice_options = []

    context = _base_context(user, "payments")
    context.update(
        {
            "active_tab": active_tab,
            "rows": rows,
            "invoice_options": invoice_options,
            "selected_invoice": invoice_id,
            "selected_method": method,
            "date_from": date_from,
            "date_to": date_to,
            "payment_errors": errors,
            "preview_mode": preview_mode,
        }
    )
    return render(request, "finance/payments.html", context)


def _load_invoices(request, preview_mode):
    if preview_mode:
        payload = _session_collection(request, "invoices")
    else:
        payload = services.get_sales_invoices(
            auth_service.access_token(request), status="OPEN"
        )
    return [
        invoice
        for invoice in presenters.invoice_rows(payload)
        if invoice["balance_value"] > 0
    ]


@require_http_methods(["GET", "POST"])
def payment_record_page(request):
    user, preview_mode, response = _page_access(
        request,
        allowed_roles=PAYMENT_CREATE_ROLES,
        label="payment recording",
    )
    if response:
        return response

    try:
        invoices = _load_invoices(request, preview_mode)
    except APIError as error:
        auth_response = _api_error_response(
            request, error, "crm_finance:payments"
        )
        if auth_response:
            return auth_response
        invoices = []
        messages.error(request, f"Could not load open invoices: {error.message}")

    initial_invoice = (
        request.GET.get("invoice_id")
        or request.POST.get("invoice_id")
        or (str(invoices[0]["id"]) if invoices else "")
    )
    form = PaymentForm(
        request.POST if request.method == "POST" else None,
        invoices=invoices,
        initial={"invoice_id": initial_invoice},
    )

    if request.method == "POST" and form.is_valid():
        payload = form.api_payload()
        if preview_mode:
            preview_invoices = _session_collection(request, "invoices")
            invoice = _find_item(preview_invoices, payload["invoice"])
            if not invoice:
                form.add_error("invoice_id", "The selected invoice was not found.")
            else:
                payment_amount = float(payload["amount"])
                balance_after = max(
                    0, float(invoice.get("balance_due") or 0) - payment_amount
                )
                invoice["balance_due"] = balance_after
                if balance_after == 0:
                    invoice["status"] = "PAID"
                _save_session_collection(request, "invoices", preview_invoices)

                preview_payments = _session_collection(request, "payments")
                payment_id = _next_numeric_id(preview_payments, 9822)
                payment = {
                    "id": payment_id,
                    "receipt_number": f"REC-{payment_id}",
                    **payload,
                    "invoice_id": payload["invoice"],
                    "invoice_number": invoice.get("invoice_number"),
                    "customer_name": invoice.get("customer_name"),
                    "vehicle": invoice.get("vehicle"),
                    "recorded_by_name": user_identity(user)["name"],
                    "balance_after": balance_after,
                }
                preview_payments.insert(0, payment)
                _save_session_collection(request, "payments", preview_payments)
                messages.success(request, "Payment recorded in preview mode.")
                return redirect(
                    "crm_finance:payment-receipt", payment_id=payment_id
                )
        else:
            try:
                result = unwrap(
                    services.create_payment(
                        auth_service.access_token(request), payload
                    )
                )
                payment_id = (
                    result.get("id") or result.get("payment_id")
                    if isinstance(result, dict)
                    else None
                )
                messages.success(request, "Payment recorded successfully.")
                if payment_id:
                    return redirect(
                        "crm_finance:payment-receipt", payment_id=payment_id
                    )
                return redirect("crm_finance:payments")
            except APIError as error:
                auth_response = _api_error_response(
                    request, error, "crm_finance:payments"
                )
                if auth_response:
                    return auth_response
                _add_api_errors(form, error)

    selected_invoice = next(
        (
            invoice
            for invoice in invoices
            if str(invoice["id"]) == str(initial_invoice)
        ),
        None,
    )
    context = _base_context(user, "payments")
    context.update(
        {
            "form": form,
            "selected_invoice": selected_invoice,
            "has_open_invoices": bool(invoices),
        }
    )
    return render(request, "finance/payment_form.html", context)


@require_GET
def payment_receipt_page(request, payment_id):
    user, preview_mode, response = _page_access(
        request,
        allowed_roles=PAYMENT_CREATE_ROLES,
        label="payment receipts",
    )
    if response:
        return response

    if preview_mode:
        payment = _find_item(
            _session_collection(request, "payments"), payment_id
        )
    else:
        try:
            payment = unwrap(
                services.get_payment(
                    auth_service.access_token(request), payment_id
                )
            )
        except APIError as error:
            if error.status_code == 404:
                raise Http404("Payment not found") from error
            auth_response = _api_error_response(
                request, error, "crm_finance:payments"
            )
            if auth_response:
                return auth_response
            messages.error(request, error.message)
            return redirect("crm_finance:payments")

    if not isinstance(payment, dict):
        raise Http404("Payment not found")

    context = _base_context(user, "payments")
    context["payment"] = presenters.payment_row(payment)
    template = (
        "finance/payment_receipt_print.html"
        if request.GET.get("print") == "1"
        else "finance/payment_receipt.html"
    )
    return render(request, template, context)


@require_GET
def payment_receipt_pdf(request, payment_id):
    user, preview_mode, response = _page_access(
        request, allowed_roles=PAYMENT_CREATE_ROLES, label="payment receipts"
    )
    if response:
        return response
    if preview_mode:
        messages.info(request, "PDF receipts require the backend API.")
        return redirect("crm_finance:payment-receipt", payment_id=payment_id)
    try:
        content = services.get_payment_receipt_pdf(
            auth_service.access_token(request), payment_id
        )
    except APIError as error:
        messages.error(request, error.message)
        return redirect("crm_finance:payment-receipt", payment_id=payment_id)
    pdf = HttpResponse(content, content_type="application/pdf")
    pdf["Content-Disposition"] = f'attachment; filename="receipt-{int(payment_id)}.pdf"'
    return pdf


@require_GET
def payments_export(request):
    user, preview_mode, response = _page_access(
        request, allowed_roles=FINANCE_ROLES, label="payment exports"
    )
    if response:
        return response

    invoice_id = request.GET.get("invoice_id", "").strip()
    method = request.GET.get("method", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    try:
        if preview_mode:
            payload = _filter_payments(
                _session_collection(request, "payments"),
                invoice_id,
                method,
                date_from,
                date_to,
            )
        else:
            content = services.export_payments(
                auth_service.access_token(request),
                invoice_id=invoice_id,
                method=method,
                date_from=date_from,
                date_to=date_to,
            )
            export = HttpResponse(content, content_type="text/csv; charset=utf-8")
            export["Content-Disposition"] = 'attachment; filename="payments-report.csv"'
            return export
        rows = presenters.payment_rows(payload)
    except APIError as error:
        messages.error(request, f"Could not export payments: {error.message}")
        return redirect("crm_finance:payments")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="payments-report.csv"'
    writer = csv.writer(response)
    writer.writerow(
        ["Receipt", "Invoice", "Customer", "Amount", "Method", "Paid At"]
    )
    for row in rows:
        writer.writerow(
            [
                row["receipt"],
                row["invoice"],
                row["customer"],
                row["amount"],
                row["method"],
                row["paid_at"],
            ]
        )
    return response


@require_GET
def finance_reports_page(request):
    user, preview_mode, response = _page_access(
        request, allowed_roles=FINANCE_ROLES, label="finance reports"
    )
    if response:
        return response

    active_tab = request.GET.get("tab", "overview")
    if active_tab not in VALID_REPORT_TABS:
        active_tab = "overview"
    vehicle_id = request.GET.get("vehicle_id", "").strip()
    errors = []
    overview = {}
    summaries = []

    if active_tab == "overview":
        try:
            payload = (
                mock_data.finance_overview()
                if preview_mode
                else services.get_finance_overview(
                    auth_service.access_token(request)
                )
            )
            overview = presenters.finance_overview(payload)
        except APIError as error:
            auth_response = _api_error_response(
                request, error, "crm_finance:finance-reports"
            )
            if auth_response:
                return auth_response
            errors.append(f"Could not load finance overview: {error.message}")
            overview = presenters.finance_overview({})
    else:
        try:
            if preview_mode:
                payload = mock_data.vehicle_summaries()
                if vehicle_id:
                    normalized = vehicle_id.lower()
                    payload = [
                        item
                        for item in payload
                        if normalized
                        in " ".join(str(value) for value in item.values()).lower()
                    ]
                summaries = presenters.vehicle_summary_rows(payload)
            elif vehicle_id:
                summaries = presenters.vehicle_summary_rows(
                    services.get_vehicle_financial_summary(
                        auth_service.access_token(request),
                        vehicle_id=vehicle_id,
                    )
                )
        except APIError as error:
            auth_response = _api_error_response(
                request, error, "crm_finance:finance-reports"
            )
            if auth_response:
                return auth_response
            errors.append(
                f"Could not load the vehicle summary: {error.message}"
            )

    context = _base_context(user, "finance")
    context.update(
        {
            "active_tab": active_tab,
            "overview": overview,
            "vehicle_summaries": summaries,
            "vehicle_query": vehicle_id,
            "report_errors": errors,
            "preview_mode": preview_mode,
        }
    )
    return render(request, "finance/reports.html", context)
