from django import forms

from loans.models import Loan

from .models import Payment


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["loan", "payment_date", "payment_mode", "transaction_id", "amount_paid", "remarks"]
        widgets = {
            "payment_date": forms.DateInput(attrs={"type": "date","min": "1900-01-01",
            "max": "9999-12-31"}),
            "payment_mode": forms.Select(),
            "transaction_id": forms.TextInput(attrs={"placeholder": "Enter transaction ID"}),
            "remarks": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["loan"].queryset = Loan.objects.filter(status=Loan.STATUS_ACTIVE)
        self.fields["remarks"].required = False

    def clean_payment_mode(self):
        return self.cleaned_data.get("payment_mode") or Payment.PAYMENT_MODE_CASH

    def clean_transaction_id(self):
        return self.cleaned_data.get("transaction_id", "").strip()

    def clean(self):
        cleaned_data = super().clean()
        mode = cleaned_data.get("payment_mode")
        transaction_id = cleaned_data.get("transaction_id")
        if mode == Payment.PAYMENT_MODE_ONLINE and not transaction_id:
            self.add_error("transaction_id", "Transaction ID is required for online payments.")
        if mode == Payment.PAYMENT_MODE_CASH:
            cleaned_data["transaction_id"] = ""
        return cleaned_data

    def clean_amount_paid(self):
        amount = self.cleaned_data["amount_paid"]
        if amount <= 0:
            raise forms.ValidationError("Amount paid must be greater than zero.")
        return amount


class PaymentEditForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["payment_date", "payment_mode", "transaction_id", "amount_paid", "remarks"]
        widgets = {
            "payment_date": forms.DateInput(attrs={"type": "date","min": "1900-01-01",
            "max": "9999-12-31"}),
            "payment_mode": forms.Select(),
            "transaction_id": forms.TextInput(attrs={"placeholder": "Enter transaction ID"}),
            "remarks": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_payment_mode(self):
        return self.cleaned_data.get("payment_mode") or Payment.PAYMENT_MODE_CASH

    def clean_transaction_id(self):
        return self.cleaned_data.get("transaction_id", "").strip()

    def clean(self):
        cleaned_data = super().clean()
        mode = cleaned_data.get("payment_mode")
        transaction_id = cleaned_data.get("transaction_id")
        if mode == Payment.PAYMENT_MODE_ONLINE and not transaction_id:
            self.add_error("transaction_id", "Transaction ID is required for online payments.")
        if mode == Payment.PAYMENT_MODE_CASH:
            cleaned_data["transaction_id"] = ""
        return cleaned_data

    def clean_amount_paid(self):
        amount = self.cleaned_data["amount_paid"]
        if amount <= 0:
            raise forms.ValidationError("Amount paid must be greater than zero.")
        return amount


class PaymentSearchForm(forms.Form):
    q = forms.CharField(required=False, label="Search (Receipt No. / Loan No. / Customer)")
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date","min": "1900-01-01",
            "max": "9999-12-31"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date","min": "1900-01-01",
            "max": "9999-12-31"}))
