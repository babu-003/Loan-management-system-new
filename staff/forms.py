from django import forms

from .models import Staff


class StaffForm(forms.ModelForm):
    class Meta:
        model = Staff
        fields = [
            "full_name", "mobile", "email", "joining_date",
            "address", "status", "notes",
        ]
        widgets = {
            "joining_date": forms.DateInput(attrs={"type": "date","min": "1900-01-01",
            "max": "9999-12-31"}),
            "address": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }


class StaffAssignmentForm(forms.Form):
    staff = forms.ModelChoiceField(
        queryset=Staff.objects.filter(status=Staff.STATUS_ACTIVE).order_by("full_name"),
        required=False,
        empty_label="— Unassigned —",
        label="Assigned Staff",
    )
