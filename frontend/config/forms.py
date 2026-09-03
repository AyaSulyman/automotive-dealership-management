from django import forms


TEXT_INPUT_ATTRIBUTES = {
    "class": "form-control",
}


class LoginForm(forms.Form):
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(
            attrs={
                **TEXT_INPUT_ATTRIBUTES,
                "placeholder": "employee@autosource.com",
                "autocomplete": "username",
                "autofocus": True,
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                **TEXT_INPUT_ATTRIBUTES,
                "placeholder": "Enter your password",
                "autocomplete": "current-password",
            }
        ),
    )
    remember_me = forms.BooleanField(
        label="Remember me on this device",
        required=False,
        widget=forms.CheckboxInput(),
    )


class EmployeeForm(forms.Form):
    ROLE_CHOICES = (
        ("", "Select a role"),
        ("admin", "Admin"),
        ("agent", "Agent"),
        ("accountant", "Accountant"),
    )

    name = forms.CharField(
        label="Full Name",
        max_length=150,
        widget=forms.TextInput(
            attrs={**TEXT_INPUT_ATTRIBUTES, "autocomplete": "name"}
        ),
    )
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(
            attrs={**TEXT_INPUT_ATTRIBUTES, "autocomplete": "email"}
        ),
    )
    password = forms.CharField(
        label="Temporary Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={**TEXT_INPUT_ATTRIBUTES, "autocomplete": "new-password"}
        ),
    )
    role = forms.ChoiceField(
        label="Role",
        choices=ROLE_CHOICES,
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, editing=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.editing = editing
        self.fields["password"].required = not editing
        if editing:
            self.fields["password"].help_text = (
                "Leave blank to keep the employee's current password."
            )

    def api_payload(self):
        payload = {
            "name": self.cleaned_data["name"],
            "email": self.cleaned_data["email"],
            "role": self.cleaned_data["role"],
        }
        if self.cleaned_data.get("password"):
            payload["password"] = self.cleaned_data["password"]
        return payload
