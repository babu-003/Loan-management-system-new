from django import forms

from .models import Investor, InvestmentLedgerEntry


class InvestorForm(forms.ModelForm):
    class Meta:
        model = Investor
        fields = ["full_name", "mobile", "email", "address"]
        widgets = {"address": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = False
        self.fields["address"].required = False


class DepositForm(forms.Form):

    investor = forms.ModelChoiceField(
        queryset=Investor.objects.filter(
            status=Investor.STATUS_ACTIVE
        )
    )

    amount = forms.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=0.01
    )

    payment_mode = forms.ChoiceField(
        choices=[
            ("cash", "Cash"),
            ("online", "Online / Bank"),
        ],
        initial="cash"
    )

    transaction_id = forms.CharField(
        max_length=100,
        required=False,
        label="Transaction ID"
    )

    notes = forms.CharField(
        max_length=255,
        required=False
    )

    def clean(self):

        cleaned = super().clean()
        # Transaction ID is optional for both payment modes. # Clear the field when Cash is selected. 
        if cleaned.get("payment_mode") == "cash": 
            cleaned["transaction_id"] = ""
        return cleaned

class DepositEditForm(forms.Form):
    amount = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0.01, label="Corrected Amount")


class LedgerFilterForm(forms.Form):
    entry_type = forms.ChoiceField(required=False, choices=[("", "All types")] + list(InvestmentLedgerEntry.TYPE_CHOICES))
    investor = forms.ModelChoiceField(required=False, queryset=Investor.objects.all())
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
