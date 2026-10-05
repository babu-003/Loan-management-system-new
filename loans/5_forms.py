from django import forms

from .models import InterestType, Installment, Loan, LoanGroup, LoanType
from staff.models import Staff


class LoanGroupForm(forms.ModelForm):
    class Meta:
        model = LoanGroup
        fields = ["group_name", "description"]


class LoanForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = [
            "customer", "assigned_staff", "loan_group", "loan_type", "interest_type",
            "principal_amount", "interest_rate", "start_date",
            "repayment_frequency", "custom_interval_days",
            "number_of_installments", "first_due_date",
            "purpose", "remarks",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date","min": "1900-01-01",
            "max": "9999-12-31"}),
            "first_due_date": forms.DateInput(attrs={"type": "date","min": "1900-01-01",
            "max": "9999-12-31"}),
            "remarks": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["loan_type"].queryset = LoanType.objects.filter(is_active=True)
        self.fields["interest_type"].queryset = InterestType.objects.filter(is_active=True)
        self.fields["loan_group"].required = False
        self.fields["assigned_staff"].required = False
        self.fields["assigned_staff"].queryset = Staff.objects.filter(
            status=Staff.STATUS_ACTIVE
        ).order_by("full_name")
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
        widgets = {"due_date": forms.DateInput(attrs={"type": "date","min": "1900-01-01",
            "max": "9999-12-31"})}


class LoanCalculatorForm(forms.Form):
    """Standalone what-if calculator — doesn't touch the database at
    all, just runs the same math real loan creation uses."""
    principal_amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=1)
    interest_rate = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, label="Interest Rate (% p.a.)")
    repayment_frequency = forms.ChoiceField(choices=Loan.FREQUENCY_CHOICES)
    custom_interval_days = forms.IntegerField(required=False, min_value=1)
    number_of_installments = forms.IntegerField(min_value=1)
    first_due_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date","min": "1900-01-01",
            "max": "9999-12-31"}),
        help_text="Optional — only used to project real due dates in the schedule preview.",
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("repayment_frequency") == Loan.FREQUENCY_CUSTOM and not cleaned_data.get("custom_interval_days"):
            self.add_error("custom_interval_days", "Required when Repayment Frequency is Custom interval.")
        return cleaned_data


class LoanSearchForm(forms.Form):
    q = forms.CharField(required=False, label="Search (Loan No. / Customer)")
    status = forms.ChoiceField(required=False, choices=[("", "All statuses")] + list(Loan.STATUS_CHOICES))
    loan_type = forms.ModelChoiceField(required=False, queryset=LoanType.objects.filter(is_active=True))
