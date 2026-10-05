from django import forms

from .models import InterestType, Installment, Loan, LoanGroup, LoanType


class LoanGroupForm(forms.ModelForm):
    class Meta:
        model = LoanGroup
        fields = ["group_name", "description"]


class LoanForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = [
            "customer", "loan_group", "loan_type", "interest_type",
            "principal_amount", "interest_rate", "start_date",
            "repayment_frequency", "custom_interval_days",
            "number_of_installments", "first_due_date",
            "purpose", "remarks",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "first_due_date": forms.DateInput(attrs={"type": "date"}),
            "remarks": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["loan_type"].queryset = LoanType.objects.filter(is_active=True)
        self.fields["interest_type"].queryset = InterestType.objects.filter(is_active=True)
        self.fields["loan_group"].required = False
        self.fields["custom_interval_days"].required = False
        for name in [
            "customer", "loan_type", "interest_type", "principal_amount",
            "interest_rate", "start_date", "repayment_frequency",
            "number_of_installments", "first_due_date",
        ]:
            self.fields[name].required = True

    def clean(self):
        cleaned_data = super().clean()
        frequency = cleaned_data.get("repayment_frequency")
        custom_interval_days = cleaned_data.get("custom_interval_days")
        if frequency == Loan.FREQUENCY_CUSTOM and not custom_interval_days:
            self.add_error(
                "custom_interval_days",
                "Required when Repayment Frequency is Custom interval.",
            )
        return cleaned_data


class InstallmentDueDateForm(forms.ModelForm):
    class Meta:
        model = Installment
        fields = ["due_date"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}


class LoanSearchForm(forms.Form):
    q = forms.CharField(required=False, label="Search (Loan No. / Customer)")
    status = forms.ChoiceField(required=False, choices=[("", "All statuses")] + list(Loan.STATUS_CHOICES))
    loan_type = forms.ModelChoiceField(required=False, queryset=LoanType.objects.filter(is_active=True))
