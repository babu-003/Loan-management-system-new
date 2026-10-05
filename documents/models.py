import os
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

ALLOWED_DOCUMENT_EXTENSIONS = ["pdf", "jpg", "jpeg", "png"]
MAX_DOCUMENT_FILE_SIZE_MB = 10


def validate_document_file_size(file):
    """Reject files above the configured size limit. Kept as a plain
    function (not a lambda) so migrations can serialize it safely."""
    limit_bytes = MAX_DOCUMENT_FILE_SIZE_MB * 1024 * 1024
    if file.size > limit_bytes:
        raise ValidationError(
            f"File is too large ({file.size / (1024 * 1024):.1f} MB). "
            f"Maximum allowed size is {MAX_DOCUMENT_FILE_SIZE_MB} MB."
        )


def customer_document_upload_path(instance, filename):
    """Store under documents/customers/<customer_id>/<uuid>.<ext> so
    filenames can never collide and files stay grouped per customer,
    per the offline local-storage layout in the project spec."""
    ext = os.path.splitext(filename)[1].lower()
    customer_id = instance.customer.customer_id if instance.customer_id else "unassigned"
    return f"documents/customers/{customer_id}/{uuid.uuid4().hex}{ext}"


class DocumentType(models.Model):
    """Admin-configurable list of document types. Scoped so the same table
    can later hold loan-document categories (Agreement, Notice, ...) too,
    but only CUSTOMER-scoped rows are used by this module."""

    SCOPE_CUSTOMER = "customer"
    SCOPE_LOAN = "loan"
    SCOPE_CHOICES = [
        (SCOPE_CUSTOMER, "Customer KYC Document"),
        (SCOPE_LOAN, "Loan Document"),
    ]

    name = models.CharField(max_length=100)
    code = models.SlugField(max_length=50, unique=True)
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default=SCOPE_CUSTOMER)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["scope", "display_order", "name"]

    def __str__(self):
        return self.name


def loan_document_upload_path(instance, filename):
    """Mirrors customer_document_upload_path but grouped per loan number:
    documents/loans/<loan_number>/<uuid>.<ext>"""
    ext = os.path.splitext(filename)[1].lower()
    loan_number = instance.loan.loan_number if instance.loan_id else "unassigned"
    return f"documents/loans/{loan_number}/{uuid.uuid4().hex}{ext}"


class LoanDocument(models.Model):
    """The loan-side counterpart to CustomerDocument — the agreement,
    application form, or closing paperwork for a specific loan, rather
    than KYC proof for a customer. Same file-or-reference-number rule."""

    STATUS_PENDING = "pending"
    STATUS_VERIFIED = "verified"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_VERIFIED, "Verified"),
        (STATUS_REJECTED, "Rejected"),
    ]

    loan = models.ForeignKey(
        "loans.Loan", on_delete=models.CASCADE, related_name="documents"
    )
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        limit_choices_to={"scope": DocumentType.SCOPE_LOAN, "is_active": True},
    )
    document_number = models.CharField(
        max_length=100, blank=True,
        help_text="Reference number, if there's no file to attach.",
    )
    file = models.FileField(
        upload_to=loan_document_upload_path, blank=True, null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS),
            validate_document_file_size,
        ],
        help_text="PDF, JPG, JPEG or PNG. Optional if a reference number is provided instead.",
    )
    uploaded_date = models.DateField(auto_now_add=True)
    verified_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    verified_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["document_type__display_order", "-uploaded_date"]

    def clean(self):
        if not self.file and not self.document_number:
            raise ValidationError(
                "Provide either an uploaded file or a reference number for this document."
            )

    def __str__(self):
        return f"{self.document_type} — {self.loan}"


class NoticeType(models.Model):
    """Admin-configurable — e.g. First Notice, Second Notice, Final Notice."""
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class Notice(models.Model):
    """A recorded notice sent to a customer about a loan — kept separate
    from LoanDocument since a notice needs a date and a reason, not just
    a file. 'document' optionally links an uploaded scan of the actual
    notice letter, if one was kept."""

    loan = models.ForeignKey("loans.Loan", on_delete=models.CASCADE, related_name="notices")
    notice_type = models.ForeignKey(NoticeType, on_delete=models.PROTECT)
    notice_date = models.DateField()
    reason = models.CharField(max_length=255)
    document = models.ForeignKey(
        LoanDocument, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="notices",
        help_text="Optional — link an uploaded scan of the notice letter itself.",
    )
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-notice_date"]

    def __str__(self):
        return f"{self.notice_type} — {self.loan.loan_number} ({self.notice_date})"


class CustomerDocument(models.Model):
    """One KYC document row for a customer. Either an uploaded file, a
    document/ID number, or both must be present — enforced in clean() so
    the rule holds no matter which form or script creates a row."""

    STATUS_PENDING = "pending"
    STATUS_VERIFIED = "verified"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_VERIFIED, "Verified"),
        (STATUS_REJECTED, "Rejected"),
    ]

    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.CASCADE, related_name="documents"
    )
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        limit_choices_to={"scope": DocumentType.SCOPE_CUSTOMER, "is_active": True},
    )
    document_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="ID / document number. Required if no file is uploaded.",
    )
    file = models.FileField(
        upload_to=customer_document_upload_path,
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS),
            validate_document_file_size,
        ],
        help_text="PDF, JPG, JPEG or PNG. Optional if a document number is provided instead.",
    )
    uploaded_date = models.DateField(auto_now_add=True)
    verified_status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    verified_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["document_type__display_order", "-uploaded_date"]

    def clean(self):
        if not self.file and not self.document_number:
            raise ValidationError(
                "Provide either an uploaded file or a document/ID number for this document."
            )

    def __str__(self):
        return f"{self.document_type} — {self.customer}"


class DocumentTemplate(models.Model):
    """The admin-editable boilerplate wording for each of the three
    generated-document categories. One row per category. The actual
    facts (customer name, loan amount, etc.) are substituted into this
    text via {{ placeholder }} tokens at generation time — see
    pdf_generator.py for the full placeholder list and rendering logic."""

    CATEGORY_AGREEMENT = "agreement"
    CATEGORY_NOTICE = "notice"
    CATEGORY_CLOSING = "closing"
    CATEGORY_CHOICES = [
        (CATEGORY_AGREEMENT, "Loan Agreement"),
        (CATEGORY_NOTICE, "Overdue Notice"),
        (CATEGORY_CLOSING, "Loan Closing Document"),
    ]

    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, unique=True)
    body = models.TextField()

    def __str__(self):
        return self.get_category_display()
