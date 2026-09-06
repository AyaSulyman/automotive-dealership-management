from uuid import uuid4
from django.contrib import messages
from django.http import HttpResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from services import auth_service
from services.access import denied
from services.api_client import APIError
from services.presenters import normalize_role, user_identity
from .sales_forms import DealForm
from . import sales_service

def access(request):
    try:
        user = auth_service.verified_user(request)
    except (auth_service.AuthenticationRequired, APIError):
        auth_service.clear_login(request)
        return None, redirect("login-page")
    if normalize_role(user.get("role")) not in {"admin", "accountant"}:
        return user, denied(request, user)
    return user, None

def context(user, **extra):
    return {"active_page": "sales", "user_identity": user_identity(user), **extra}

def api_errors(form, error):
    applied = False
    for key, values in error.field_errors.items():
        if not isinstance(values, (list, tuple)):
            values = [values]
        for value in values:
            form.add_error(key if key in form.fields else None, str(value))
            applied = True
    if not applied:
        form.add_error(None, error.message)

@require_http_methods(["GET"])
def deal_list_page(request):
    user, failure = access(request)
    if failure:
        return failure
    search, status = request.GET.get("search", "").strip(), request.GET.get("status", "")
    try:
        page = max(1, int(request.GET.get("page", "1")))
    except ValueError:
        page = 1
    payload = {}
    error_message = ""
    try:
        payload = sales_service.invoices(auth_service.access_token(request), search=search, status=status, page=page, page_size=20)
    except APIError as error:
        error_message = error.message
    return render(request, "sales/deals.html", context(user,
        invoices=payload.get("results", []), total=payload.get("count", 0),
        search=search, status=status, page=page, previous_page=page-1 if payload.get("previous") else None,
        next_page=page+1 if payload.get("next") else None, load_error=error_message))

@require_http_methods(["GET", "POST"])
def deal_add_page(request, deal_id=None):
    user, failure = access(request)
    if failure:
        return failure
    token = auth_service.access_token(request)
    invoice = None
    customers, vehicles = [], []
    load_error = None
    try:
        if deal_id:
            invoice = sales_service.invoice(token, deal_id)
            if invoice["status"] != "DRAFT":
                return redirect("inventory:deal-invoice", deal_id=deal_id)
        customers, vehicles = sales_service.options(token, deal_id)
    except APIError as error:
        if error.status_code == 404:
            raise Http404("Deal not found")
        load_error = error
    initial = {}
    if invoice:
        initial = {key: invoice.get(key) for key in ("customer_id", "vehicle_id", "selling_price", "discount_amount")}
        initial["trade_in_value"] = invoice.get("trade_in_credit", "0")
        initial["trade_in_details"] = "\n".join(row.get("condition_notes", "") for row in invoice.get("trade_ins", []))
    pending = request.session.get("adms_deal_submissions", {})
    if request.method == "GET":
        key = uuid4().hex
        pending[key] = None
        request.session["adms_deal_submissions"] = dict(list(pending.items())[-30:])
        initial["submission_key"] = key
    form = DealForm(request.POST if request.method == "POST" else None, initial=initial, customers=customers, vehicles=vehicles)
    quote = invoice
    if load_error:
        api_errors(form, load_error)
    if request.method == "POST" and not load_error and form.is_valid():
        key = form.cleaned_data["submission_key"]
        action = request.POST.get("action", "quote")
        if key not in pending:
            form.add_error(None, "This form has expired. Open a new deal form and try again.")
        elif pending[key]:
            return redirect("inventory:deal-invoice", deal_id=pending[key])
        elif action not in {"quote", "draft", "finalize"}:
            form.add_error(None, "Choose Calculate totals, Save draft, or Finalize.")
        else:
            try:
                result = sales_service.worksheet(token, form.api_payload(action, deal_id))
                if action == "quote":
                    quote = result
                else:
                    pending[key] = result["id"]
                    request.session["adms_deal_submissions"] = pending
                    messages.success(request, "Deal finalized." if action == "finalize" else "Draft saved.")
                    return redirect("inventory:deal-invoice", deal_id=result["id"])
            except APIError as error:
                api_errors(form, error)
    return render(request, "sales/create_deal.html", context(user, form=form, deal=invoice, quote=quote, is_edit=bool(deal_id)))

deal_edit_page = deal_add_page

@require_http_methods(["GET"])
def deal_invoice_view(request, deal_id):
    user, failure = access(request)
    if failure:
        return failure
    try:
        invoice = sales_service.invoice(auth_service.access_token(request), deal_id)
    except APIError as error:
        if error.status_code == 404:
            raise Http404("Deal not found")
        messages.error(request, error.message)
        return redirect("inventory:deal-list")
    return render(request, "sales/invoice.html", context(user, invoice=invoice))

deal_detail_page = deal_invoice_view

@require_http_methods(["GET"])
def deal_invoice_pdf(request, deal_id):
    user, failure = access(request)
    if failure:
        return failure
    try:
        content = sales_service.invoice_pdf(auth_service.access_token(request), deal_id)
    except APIError as error:
        messages.error(request, error.message)
        return redirect("inventory:deal-invoice", deal_id=deal_id)
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="invoice-{int(deal_id)}.pdf"'
    return response
