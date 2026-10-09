from django import forms

from .models import CustomerDocument, DocumentType


class DocumentEditForm(forms.ModelForm):
    """Corrects an existing document row (wrong number, replace a bad
    scan). Verification status is deliberately NOT editable here — that
    stays a separate action (see verify_customer_document in the
    customers app) so the two workflows never fight over the same field.
    """

    class Meta:
        model = CustomerDocument
        fields = ["document_type", "document_number", "file", "remarks"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["document_type"].queryset = DocumentType.objects.filter(
            scope=DocumentType.SCOPE_CUSTOMER, is_active=True
        )

    def clean(self):
        cleaned_data = super().clean()
        document_number = cleaned_data.get("document_number")
        # `file` may be an already-saved FieldFile even if nothing new is
        # uploaded this time, so check the instance's existing file too.
        has_file = bool(cleaned_data.get("file")) or bool(self.instance.file)
        if not document_number and not has_file:
            raise forms.ValidationError(
                "Provide either an uploaded file or a document/ID number."
            )
        return cleaned_data


class DocumentManagementSearchForm(forms.Form):
    q = forms.CharField(required=False, label="Search (Customer ID / Name / Doc. Number)")
    document_type = forms.ModelChoiceField(
        required=False,
        queryset=DocumentType.objects.filter(scope=DocumentType.SCOPE_CUSTOMER),
    )
    verified_status = forms.ChoiceField(
        required=False,
        choices=[("", "All statuses")] + list(CustomerDocument.STATUS_CHOICES),
    )
    show_archived = forms.BooleanField(required=False, label="Show archived only")


from .models import LoanDocument, Notice, NoticeType  # noqa: E402


class LoanDocumentForm(forms.Form):
    document_type = forms.ModelChoiceField(
        queryset=DocumentType.objects.filter(scope=DocumentType.SCOPE_LOAN, is_active=True),
    )
    document_number = forms.CharField(
        max_length=100, required=False,
        help_text="Fill this in if there's no file to attach.",
    )
    file = forms.FileField(required=False, help_text="PDF, JPG, JPEG or PNG, up to 10 MB.")
    remarks = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("document_number") and not cleaned_data.get("file"):
            raise forms.ValidationError(
                "Provide either an uploaded file or a reference number."
            )
        return cleaned_data


class NoticeForm(forms.ModelForm):
    class Meta:
        model = Notice
        fields = ["notice_type", "notice_date", "reason", "document", "remarks"]
        widgets = {
            "notice_date": forms.DateInput(attrs={"type": "date"}),
            "remarks": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, loan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["notice_type"].queryset = NoticeType.objects.filter(is_active=True)
        self.fields["document"].required = False
        if loan is not None:
            self.fields["document"].queryset = LoanDocument.objects.filter(loan=loan)


from .models import DocumentTemplate  # noqa: E402


class DocumentTemplateForm(forms.ModelForm):
    class Meta:
        model = DocumentTemplate
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 18})}


class GeneratedDocumentPreviewForm(forms.Form):
    """The final editable text shown before download — pre-filled with
    the template's wording after placeholder substitution, but the
    admin can tweak it for this one document without touching the
    underlying template."""
    body_text = forms.CharField(widget=forms.Textarea(attrs={"rows": 16}))
