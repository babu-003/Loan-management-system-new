from django import forms
from django.forms import formset_factory

from documents.models import DocumentType

from .models import Customer, CustomerBankDetail
from staff.models import Staff


class PersonalDetailsForm(forms.ModelForm):
    """Step 1 of the customer wizard.

    `customer_category` is NOT a model field. Group vs individual is a
    decision that belongs to Loan/LoanGroup in this system's design (a
    customer must stay an independent record whether or not they end up
    in a group loan) — this field only tailors the confirmation message
    shown after the customer is saved, pointing the admin to the right
    next step. Nothing about it is persisted on Customer.
    """

    CATEGORY_INDIVIDUAL = "individual"
    CATEGORY_GROUP = "group"

    customer_category = forms.ChoiceField(
        choices=[
            (CATEGORY_INDIVIDUAL, "Individual customer (will take an individual loan)"),
            (CATEGORY_GROUP, "Will be added to a loan group"),
        ],
        widget=forms.RadioSelect,
        initial=CATEGORY_INDIVIDUAL,
        label="Customer category",
        help_text="Informational only — actual group membership is set when a loan is created.",
    )

    class Meta:
        model = Customer
        fields = [
            "full_name",
            "date_of_birth",
            "gender",
            "mobile",
            "alternate_mobile",
            "email",
            "photo",
            "marital_status",
            "occupation",
            "monthly_income",
            "father_husband_name",
            "status",
            "default_staff",
        ]
        labels = {
        "father_husband_name": "Father/Husband Name",
    }

        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date","min": "1900-01-01",
            "max": "9999-12-31"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Everything compulsory except the two fields that are genuinely
        # optional in normal practice (a second mobile number and email).
        optional_fields = {"alternate_mobile", "email", "photo"}
        for field_name, field in self.fields.items():
            if field_name not in optional_fields and field_name != "customer_category":
                field.required = True
        self.fields["default_staff"].queryset = Staff.objects.filter(
            status=Staff.STATUS_ACTIVE
        ).order_by("full_name")
        self.fields["default_staff"].required = False
        self.fields["default_staff"].label = "Default Staff (Optional)"
        self.fields["default_staff"].help_text = "You can assign or change the staff member later from the loan."


class AddressForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "permanent_door_no",
            "permanent_street",
            "permanent_area",
            "permanent_village_town",
            "permanent_city",
            "permanent_district",
            "permanent_state",
            "permanent_pincode",
            "same_as_permanent_address",
            "current_door_no",
            "current_street",
            "current_area",
            "current_village_town",
            "current_city",
            "current_district",
            "current_state",
            "current_pincode",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in [
            "permanent_door_no", "permanent_street", "permanent_area",
            "permanent_village_town", "permanent_city", "permanent_district",
            "permanent_state", "permanent_pincode",
        ]:
            self.fields[field_name].required = True
        for field_name in [
            "current_door_no", "current_street", "current_area",
            "current_village_town", "current_city", "current_district",
            "current_state", "current_pincode",
        ]:
            self.fields[field_name].required = False

    def clean(self):
        cleaned_data = super().clean()
        same_as_permanent = cleaned_data.get("same_as_permanent_address")
        if not same_as_permanent:
            current_fields = [
                "current_door_no", "current_street", "current_area",
                "current_village_town", "current_city", "current_district",
                "current_state", "current_pincode",
            ]
            for field_name in current_fields:
                if not cleaned_data.get(field_name):
                    self.add_error(
                        field_name,
                        "Required because the current address is different "
                        "from the permanent address.",
                    )
        return cleaned_data


class ReferenceForm(forms.Form):
    reference_name = forms.CharField(max_length=150)
    reference_mobile = forms.CharField(max_length=10)
    reference_address = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))
    relationship = forms.CharField(max_length=100)


class BaseReferenceFormSet(forms.BaseFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        filled_forms = [
            form for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False)
        ]
        if not filled_forms:
            raise forms.ValidationError(
                "At least one reference/family contact is required."
            )


ReferenceFormSet = formset_factory(
    ReferenceForm,
    formset=BaseReferenceFormSet,
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
)


class BankDetailForm(forms.ModelForm):
    class Meta:
        model = CustomerBankDetail
        fields = [
            "account_holder_name",
            "bank_name",
            "branch",
            "account_number",
            "ifsc",
            "account_type",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = True


class DocumentForm(forms.Form):
    document_type = forms.ModelChoiceField(
        queryset=DocumentType.objects.filter(
            scope=DocumentType.SCOPE_CUSTOMER, is_active=True
        ),
        required=False,
    )
    document_number = forms.CharField(
        max_length=100,
        required=False,
        help_text="Fill this in if there is no photo/file proof for this document.",
    )
    file = forms.FileField(
        required=False,
        help_text="PDF, JPG, JPEG or PNG, up to 10 MB.",
    )
    remarks = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 1}), required=False
    )

    def clean(self):
        cleaned_data = super().clean()
        document_type = cleaned_data.get("document_type")
        document_number = cleaned_data.get("document_number")
        file = cleaned_data.get("file")

        # An entirely empty extra row is fine — it just gets skipped.
        if not document_type and not document_number and not file:
            return cleaned_data

        if not document_type:
            self.add_error("document_type", "Select the document type.")

        if not document_number and not file:
            raise forms.ValidationError(
                "Provide either an uploaded file, or the document/ID number "
                "if there is no photo/file proof available."
            )
        return cleaned_data


class BaseDocumentFormSet(forms.BaseFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        filled_forms = [
            form for form in self.forms
            if form.cleaned_data and form.cleaned_data.get("document_type")
        ]
        if not filled_forms:
            raise forms.ValidationError(
                "At least one KYC document (file or ID number) is required."
            )


DocumentFormSet = formset_factory(
    DocumentForm,
    formset=BaseDocumentFormSet,
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
)


class CustomerSearchForm(forms.Form):
    q = forms.CharField(required=False, label="Search")
    status = forms.ChoiceField(
        required=False,
        choices=[("", "All statuses")] + list(Customer.STATUS_CHOICES),
    )
    created_from = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date","min": "1900-01-01",
            "max": "9999-12-31",})
    )
    created_to = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date","min": "1900-01-01",
            "max": "9999-12-31",})
    )
    location = forms.CharField(required=False)
