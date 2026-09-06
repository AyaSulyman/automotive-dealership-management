from decimal import Decimal
from django import forms

CONTROL = {"class": "inventory-form-control"}


class DealForm(forms.Form):
    customer_id = forms.ChoiceField(label="Customer", widget=forms.Select(attrs=CONTROL))
    vehicle_id = forms.ChoiceField(label="Available vehicle", widget=forms.Select(attrs=CONTROL))
    selling_price = forms.DecimalField(label="Selling price", max_digits=12, decimal_places=2, min_value=Decimal("0.01"), widget=forms.NumberInput(attrs={**CONTROL, "step": "0.01"}))
    discount_amount = forms.DecimalField(label="Discount", max_digits=12, decimal_places=2, min_value=0, initial=0, widget=forms.NumberInput(attrs={**CONTROL, "step": "0.01"}))
    trade_in_value = forms.DecimalField(label="Trade-in appraisal value", max_digits=12, decimal_places=2, min_value=0, initial=0, widget=forms.NumberInput(attrs={**CONTROL, "step": "0.01"}))
    trade_in_details = forms.CharField(label="Trade-in details", required=False, max_length=2000, widget=forms.Textarea(attrs={**CONTROL, "rows": 3}))
    submission_key = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, customers=(), vehicles=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer_id"].choices = [("", "Select customer")] + [(str(row["id"]), row["name"]) for row in customers]
        self.fields["vehicle_id"].choices = [("", "Select available vehicle")] + [(str(row["id"]), f'{row["name"]} — {row["vin"]}' + (f' — List price {row["selling_price"]}' if row.get("selling_price") else "")) for row in vehicles]

    def api_payload(self, action, invoice_id=None):
        data = {name: str(self.cleaned_data[name]) for name in ("selling_price", "discount_amount", "trade_in_value")}
        data.update(customer_id=int(self.cleaned_data["customer_id"]), vehicle_id=int(self.cleaned_data["vehicle_id"]), trade_in_details=self.cleaned_data["trade_in_details"], action=action)
        if invoice_id:
            data["invoice_id"] = int(invoice_id)
        return data
