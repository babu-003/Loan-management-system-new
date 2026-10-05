from django import forms

from loans.models import Loan

from .models import Payment


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["loan", "payment_date", "amount_paid", "remarks"]
        widgets = {
            "payment_date": forms.DateInput(attrs={"type": "date"}),
            "remarks": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["loan"].queryset = Loan.objects.filter(status=Loan.STATUS_ACTIVE)
        self.fields["remarks"].required = False

    def clean_amount_paid(self):
        amount = self.cleaned_data["amount_paid"]
        if amount <= 0:
            raise forms.ValidationError("Amount paid must be greater than zero.")
        return amount


class PaymentEditForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["payment_date", "amount_paid", "remarks"]
        widgets = {
            "payment_date": forms.DateInput(attrs={"type": "date"}),
            "remarks": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_amount_paid(self):
        amount = self.cleaned_data["amount_paid"]
        if amount <= 0:
            raise forms.ValidationError("Amount paid must be greater than zero.")
        return amount


class PaymentSearchForm(forms.Form):
    q = forms.CharField(required=False, label="Search (Receipt No. / Loan No. / Customer)")
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
