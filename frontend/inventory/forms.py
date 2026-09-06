from datetime import date

from django import forms


FORM_CONTROL = {"class": "inventory-form-control"}


class VehicleForm(forms.Form):
    STATUS_CHOICES = (
        ("IN_TRANSIT", "In Transit"),
        ("RECEIVED", "Received"),
        ("UNDER_RECONDITIONING", "Under Reconditioning"),
        ("AVAILABLE", "Available"),
        ("RESERVED", "Reserved"),
        ("SOLD", "Sold"),
        ("RETURNED", "Returned"),
    )
    CONDITION_CHOICES = (
        ("New", "New"),
        ("Used", "Used"),
        ("Certified", "Certified"),
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
        max_length=80,
        widget=forms.TextInput(attrs={**FORM_CONTROL, "placeholder": "Toyota"}),
    )
    model = forms.CharField(
        max_length=80,
        widget=forms.TextInput(attrs={**FORM_CONTROL, "placeholder": "Corolla"}),
    )
    year = forms.IntegerField(
        min_value=1900,
        max_value=date.today().year + 1,
        widget=forms.NumberInput(attrs=FORM_CONTROL),
    )
    trim = forms.CharField(
        max_length=80,
        required=False,
        widget=forms.TextInput(attrs={**FORM_CONTROL, "placeholder": "LE"}),
    )
    condition = forms.ChoiceField(
        choices=CONDITION_CHOICES,
        widget=forms.Select(attrs=FORM_CONTROL),
    )
    purchase_order_id = forms.CharField(
        label="Purchase Order",
        max_length=80,
        required=False,
        widget=forms.TextInput(attrs={**FORM_CONTROL, "placeholder": "PO-8821"}),
    )
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
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

    def clean_vin(self):
        return self.cleaned_data["vin"].strip().upper()

    def api_payload(self):
        return {
            "vin": self.cleaned_data["vin"],
            "make": self.cleaned_data["make"],
            "model": self.cleaned_data["model"],
            "year": self.cleaned_data["year"],
            "trim": self.cleaned_data["trim"],
            "condition": self.cleaned_data["condition"],
            "purchase_order_id": self.cleaned_data["purchase_order_id"] or None,
            "status": self.cleaned_data["status"],
            "acquisition_cost": float(self.cleaned_data["acquisition_cost"]),
            "transport_cost": float(self.cleaned_data["transport_cost"]),
            "recon_cost": float(self.cleaned_data["recon_cost"]),
        }


class VendorForm(forms.Form):
    name = forms.CharField(
        label="Vendor Name",
        max_length=150,
        widget=forms.TextInput(attrs=FORM_CONTROL),
    )
    contact_name = forms.CharField(
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
    payment_terms = forms.CharField(
        max_length=80,
        required=False,
        widget=forms.TextInput(
            attrs={**FORM_CONTROL, "placeholder": "Net 30"}
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
            "contact_name": self.cleaned_data["contact_name"],
            "phone": self.cleaned_data["phone"],
            "email": self.cleaned_data["email"],
            "payment_terms": self.cleaned_data["payment_terms"],
            "is_active": self.cleaned_data["is_active"],
        }


class PurchaseOrderStatusForm(forms.Form):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("RECEIVED", "Received"),
        ("CLOSED", "Closed"),
    )
    status = forms.ChoiceField(choices=STATUS_CHOICES)


class DealForm(forms.Form):
    DEAL_STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("CLOSED", "Closed"),
    )

    customer = forms.CharField(
        max_length=100,
        widget=forms.Select(
            choices=[('', 'Select Customer'), ('1', 'Eleanor Vance')],
            attrs=FORM_CONTROL
        )
    )
    vehicle = forms.CharField(
        widget=forms.Select(
            choices=[('', 'Select Available Vehicle'), ('v1', '2024 Veloce Executive Sedan')],
            attrs=FORM_CONTROL
        )
    )
    sale_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=54200.00,
        widget=forms.NumberInput(attrs={**FORM_CONTROL, "step": "0.01"})
    )
    discount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=-1500.00,
        required=False,
        widget=forms.NumberInput(attrs={**FORM_CONTROL, "step": "0.01"})
    )
    tax = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=4216.00,
        widget=forms.NumberInput(attrs={**FORM_CONTROL, "step": "0.01"})
    )
    trade_in_details = forms.CharField(
        widget=forms.Textarea(attrs={**FORM_CONTROL, 'rows': 2, 'placeholder': '2018 Horizon SUV - Black'}),
        required=False
    )
    status = forms.ChoiceField(
        choices=DEAL_STATUS_CHOICES,
        widget=forms.Select(attrs=FORM_CONTROL)
    )

    def api_payload(self):
        return {
            "customer": self.cleaned_data["customer"],
            "vehicle": self.cleaned_data["vehicle"],
            "sale_price": float(self.cleaned_data["sale_price"]),
            "discount": float(self.cleaned_data["discount"] or 0),
            "tax": float(self.cleaned_data["tax"]),
            "trade_in_details": self.cleaned_data["trade_in_details"],
            "status": self.cleaned_data["status"],
        }