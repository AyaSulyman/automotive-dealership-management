from datetime import date

from django import forms


FORM_CONTROL = {"class": "inventory-form-control"}


class VehicleForm(forms.Form):
    STATUS_CHOICES = (
        ("IN_TRANSIT", "In Transit"),
        ("IN_STOCK", "In Stock"),
        ("AVAILABLE", "Available"),
    )
    CONDITION_CHOICES = (
        ("NEW", "New"),
        ("USED", "Used"),
    )

    vin = forms.CharField(
        label="VIN",
        min_length=17,
        max_length=17,
        widget=forms.TextInput(
            attrs={
                **FORM_CONTROL,
                "placeholder": "17-character VIN",
                "autocomplete": "off",
            }
        ),
    )
    make = forms.CharField(
        max_length=60,
        widget=forms.TextInput(attrs={**FORM_CONTROL, "placeholder": "Toyota"}),
    )
    model = forms.CharField(
        max_length=60,
        widget=forms.TextInput(attrs={**FORM_CONTROL, "placeholder": "Corolla"}),
    )
    year = forms.IntegerField(
        min_value=1900,
        max_value=date.today().year + 1,
        widget=forms.NumberInput(attrs=FORM_CONTROL),
    )
    trim = forms.CharField(
        max_length=60,
        required=False,
        widget=forms.TextInput(attrs={**FORM_CONTROL, "placeholder": "LE"}),
    )
    condition = forms.ChoiceField(
        choices=CONDITION_CHOICES,
        initial="USED",
        widget=forms.Select(attrs=FORM_CONTROL),
    )
    purchase_order_id = forms.ChoiceField(
        label="Purchase Order",
        required=False,
        choices=(),
        widget=forms.Select(attrs=FORM_CONTROL),
    )
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        initial="AVAILABLE",
        widget=forms.Select(attrs=FORM_CONTROL),
    )
    acquisition_cost = forms.DecimalField(
        min_value=0,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={**FORM_CONTROL, "step": "0.01"}),
    )
    transport_cost = forms.DecimalField(
        min_value=0,
        max_digits=12,
        decimal_places=2,
        initial=0,
        widget=forms.NumberInput(attrs={**FORM_CONTROL, "step": "0.01"}),
    )
    recon_cost = forms.DecimalField(
        label="Reconditioning Cost",
        min_value=0,
        max_digits=12,
        decimal_places=2,
        initial=0,
        widget=forms.NumberInput(attrs={**FORM_CONTROL, "step": "0.01"}),
    )

    selling_price = forms.DecimalField(label="List price", min_value=0, max_digits=12, decimal_places=2, required=False, widget=forms.NumberInput(attrs={**FORM_CONTROL, "step": "0.01"}))

    def clean_vin(self):
        return self.cleaned_data["vin"].strip().upper()

    def __init__(self, *args, purchase_orders=None, **kwargs):
        super().__init__(*args, **kwargs)
        purchase_orders = purchase_orders or []
        self.fields["purchase_order_id"].choices = [("", "No purchase order")] + [
            (
                str(order["id"]),
                f'{order["number"]} — {order["vendor"]}',
            )
            for order in purchase_orders
            if order.get("id") not in (None, "")
        ]

    def api_payload(self):
        return {
            "vin": self.cleaned_data["vin"],
            "make": self.cleaned_data["make"],
            "model": self.cleaned_data["model"],
            "year": self.cleaned_data["year"],
            "trim": self.cleaned_data["trim"],
            "condition": self.cleaned_data["condition"],
            "purchase_order_id": (
                int(self.cleaned_data["purchase_order_id"])
                if str(self.cleaned_data["purchase_order_id"]).isdigit()
                else self.cleaned_data["purchase_order_id"] or None
            ),
            "status": self.cleaned_data["status"],
            "selling_price": str(self.cleaned_data["selling_price"]) if self.cleaned_data["selling_price"] is not None else None,
            "acquisition_cost": str(self.cleaned_data["acquisition_cost"]),
            "transport_cost": str(self.cleaned_data["transport_cost"]),
            "recon_cost": str(self.cleaned_data["recon_cost"]),
        }


class VendorForm(forms.Form):
    name = forms.CharField(
        label="Vendor Name",
        max_length=150,
        widget=forms.TextInput(attrs=FORM_CONTROL),
    )
    contact_person = forms.CharField(
        label="Contact Person",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs=FORM_CONTROL),
    )
    phone = forms.CharField(
        max_length=40,
        required=False,
        widget=forms.TextInput(attrs=FORM_CONTROL),
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs=FORM_CONTROL),
    )
    address = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={**FORM_CONTROL, "placeholder": "Vendor address"}
        ),
    )
    is_active = forms.BooleanField(
        label="Active vendor",
        required=False,
        initial=True,
    )

    def api_payload(self):
        return {
            "name": self.cleaned_data["name"],
            "contact_person": self.cleaned_data["contact_person"],
            "phone": self.cleaned_data["phone"],
            "email": self.cleaned_data["email"],
            "address": self.cleaned_data["address"],
            "is_active": self.cleaned_data["is_active"],
        }


class PurchaseOrderStatusForm(forms.Form):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("RECEIVED", "Received"),
        ("CLOSED", "Closed"),
    )

    status = forms.ChoiceField(choices=STATUS_CHOICES)


class DocumentForm(forms.Form):
    DOC_TYPE_CHOICES = (
        ("TITLE", "Title"),
        ("ID", "ID"),
        ("CONTRACT", "Contract"),
        ("INSPECTION", "Inspection"),
        ("BILL_OF_SALE", "Bill of Sale"),
    )
    doc_type = forms.ChoiceField(label="Document type", choices=DOC_TYPE_CHOICES, widget=forms.Select(attrs=FORM_CONTROL))
    file = forms.FileField(
        label="File",
        help_text="PDF, PNG, JPG, or JPEG. Maximum 10 MB.",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.png,.jpg,.jpeg"}),
    )

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if uploaded.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Files must be 10 MB or smaller.")
        if not uploaded.name.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
            raise forms.ValidationError("Upload a PDF, PNG, JPG, or JPEG file.")
        return uploaded
