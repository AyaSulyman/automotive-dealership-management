from django import forms
from django.utils import timezone


FORM_CONTROL = {"class": "business-form-control"}


class CustomerForm(forms.Form):
    ID_TYPE_CHOICES = (
        ("", "Select ID type"),
        ("DL", "Driver's License"),
        ("NATIONAL_ID", "National ID"),
        ("PASSPORT", "Passport"),
    )
    STATUS_CHOICES = (
        ("LEAD", "Lead"),
        ("ACTIVE", "Active"),
        ("VIP", "VIP"),
        ("INACTIVE", "Inactive"),
    )

    full_name = forms.CharField(
        label="Full Name",
        max_length=150,
        widget=forms.TextInput(
            attrs={**FORM_CONTROL, "placeholder": "Customer full name"}
        ),
    )
    id_type = forms.ChoiceField(
        label="ID Type",
        required=False,
        choices=ID_TYPE_CHOICES,
        widget=forms.Select(attrs=FORM_CONTROL),
    )
    id_number = forms.CharField(
        label="ID Number",
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs=FORM_CONTROL),
    )
    phone = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(
            attrs={**FORM_CONTROL, "placeholder": "+961 00 000 000"}
        ),
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(
            attrs={**FORM_CONTROL, "placeholder": "customer@example.com"}
        ),
    )
    address = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs=FORM_CONTROL),
    )
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        initial="ACTIVE",
        widget=forms.Select(attrs=FORM_CONTROL),
    )

    def clean_full_name(self):
        return " ".join(self.cleaned_data["full_name"].split())

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("phone") and not cleaned.get("email"):
            raise forms.ValidationError(
                "Enter at least a phone number or an email address."
            )
        return cleaned

    def api_payload(self):
        name_parts = self.cleaned_data["full_name"].split(maxsplit=1)
        return {
            "first_name": name_parts[0],
            "last_name": name_parts[1] if len(name_parts) > 1 else "",
            "id_type": self.cleaned_data["id_type"],
            "id_number": self.cleaned_data["id_number"],
            "phone": self.cleaned_data["phone"],
            "email": self.cleaned_data["email"],
            "address": self.cleaned_data["address"],
            "status": self.cleaned_data["status"],
        }


class PaymentForm(forms.Form):
    METHOD_CHOICES = (
        ("CASH", "Cash"),
        ("CARD", "Card"),
        ("TRANSFER", "Bank Transfer"),
        ("CHECK", "Check"),
        ("ACH", "ACH"),
    )

    invoice_id = forms.ChoiceField(
        label="Link to Invoice",
        choices=(),
        widget=forms.Select(attrs=FORM_CONTROL),
    )
    amount = forms.DecimalField(
        label="Payment Amount",
        min_value=0.01,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={**FORM_CONTROL, "min": "0.01", "step": "0.01"}
        ),
    )
    method = forms.ChoiceField(
        label="Payment Method",
        choices=METHOD_CHOICES,
        widget=forms.Select(attrs=FORM_CONTROL),
    )
    paid_at = forms.DateTimeField(
        label="Paid At",
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={**FORM_CONTROL, "type": "datetime-local"},
        ),
    )
    reference_number = forms.CharField(
        label="Reference Number",
        max_length=60,
        required=False,
        widget=forms.TextInput(
            attrs={
                **FORM_CONTROL,
                "placeholder": "Bank, card, or transaction reference",
            }
        ),
    )

    def __init__(self, *args, invoices=None, **kwargs):
        super().__init__(*args, **kwargs)
        invoices = invoices or []
        self.invoice_map = {
            str(invoice["id"]): invoice for invoice in invoices if invoice.get("id")
        }
        self.fields["invoice_id"].choices = [
            (
                str(invoice["id"]),
                (
                    f'{invoice["number"]} — {invoice["customer"]} '
                    f'— {invoice["balance_display"]}'
                ),
            )
            for invoice in invoices
            if invoice.get("id")
        ]
        if not self.is_bound:
            self.fields["paid_at"].initial = timezone.localtime().strftime(
                "%Y-%m-%dT%H:%M"
            )

    def clean(self):
        cleaned = super().clean()
        invoice = self.invoice_map.get(str(cleaned.get("invoice_id", "")))
        amount = cleaned.get("amount")
        if invoice and amount is not None and amount > invoice["balance_value"]:
            self.add_error(
                "amount",
                "The payment cannot be greater than the current balance.",
            )
        return cleaned

    def api_payload(self):
        invoice_id = self.cleaned_data["invoice_id"]
        return {
            "invoice": int(invoice_id) if str(invoice_id).isdigit() else invoice_id,
            "amount": str(self.cleaned_data["amount"]),
            "method": self.cleaned_data["method"],
            "paid_at": self.cleaned_data["paid_at"].isoformat(),
            "reference_number": self.cleaned_data["reference_number"],
        }
