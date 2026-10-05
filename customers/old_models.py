from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models, transaction

mobile_validator = RegexValidator(
    regex=r"^[6-9]\d{9}$",
    message="Enter a valid 10-digit mobile number.",
)
pincode_validator = RegexValidator(
    regex=r"^\d{6}$",
    message="Enter a valid 6-digit pincode.",
)
ifsc_validator = RegexValidator(
    regex=r"^[A-Z]{4}0[A-Z0-9]{6}$",
    message="Enter a valid IFSC code (e.g. HDFC0001234).",
)


class CustomerIDCounter(models.Model):
    """Single-row counter used to generate CUS-000001 style IDs.
    Kept local to the customers app (not the shared core.IDSequence from
    the full design) since the core app hasn't been built yet — this can
    be swapped out later without changing anything on Customer itself."""

    last_number = models.PositiveIntegerField(default=0)

    @classmethod
    def next_customer_id(cls):     # (or next_loan_number / next_group_id / next_receipt_number)
        from core.models import get_setting
        prefix = get_setting("customer_id_prefix", "CUS")   # matching key per file, see below
        padding = int(get_setting("id_number_padding", "6"))
        with transaction.atomic():
            counter, _ = cls.objects.select_for_update().get_or_create(pk=1)
            counter.last_number += 1
            counter.save(update_fields=["last_number"])
            return f"{prefix}-{counter.last_number:0{padding}d}"


class Customer(models.Model):
    GENDER_MALE = "male"
    GENDER_FEMALE = "female"
    GENDER_OTHER = "other"
    GENDER_CHOICES = [
        (GENDER_MALE, "Male"),
        (GENDER_FEMALE, "Female"),
        (GENDER_OTHER, "Other"),
    ]

    MARITAL_SINGLE = "single"
    MARITAL_MARRIED = "married"
    MARITAL_OTHER = "other"
    MARITAL_CHOICES = [
        (MARITAL_SINGLE, "Single"),
        (MARITAL_MARRIED, "Married"),
        (MARITAL_OTHER, "Other"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_INACTIVE, "Inactive"),
    ]

    # --- Identity -----------------------------------------------------
    customer_id = models.CharField(max_length=20, unique=True, editable=False)

    # --- Personal details ----------------------------------------------
    full_name = models.CharField(max_length=150)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    mobile = models.CharField(max_length=10, validators=[mobile_validator], unique=True)
    alternate_mobile = models.CharField(
        max_length=10, validators=[mobile_validator], blank=True
    )
    email = models.EmailField(blank=True)
    photo = models.ImageField(upload_to="customers/photos/", blank=True, null=True)
    marital_status = models.CharField(max_length=10, choices=MARITAL_CHOICES)
    occupation = models.CharField(max_length=100)
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2)
    father_husband_name = models.CharField(max_length=150)

    # --- Permanent address ----------------------------------------------
    permanent_door_no = models.CharField(max_length=50)
    permanent_street = models.CharField(max_length=150)
    permanent_area = models.CharField(max_length=150)
    permanent_village_town = models.CharField(max_length=150)
    permanent_city = models.CharField(max_length=100)
    permanent_district = models.CharField(max_length=100)
    permanent_state = models.CharField(max_length=100)
    permanent_pincode = models.CharField(max_length=6, validators=[pincode_validator])

    # --- Current address (mirrors permanent address fields) -------------
    same_as_permanent_address = models.BooleanField(default=True)
    current_door_no = models.CharField(max_length=50, blank=True)
    current_street = models.CharField(max_length=150, blank=True)
    current_area = models.CharField(max_length=150, blank=True)
    current_village_town = models.CharField(max_length=150, blank=True)
    current_city = models.CharField(max_length=100, blank=True)
    current_district = models.CharField(max_length=100, blank=True)
    current_state = models.CharField(max_length=100, blank=True)
    current_pincode = models.CharField(max_length=6, blank=True)

    # --- Status / bookkeeping -------------------------------------------
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.customer_id} — {self.full_name}"

    def clean(self):
        if not self.same_as_permanent_address:
            required_current_fields = {
                "current_door_no": self.current_door_no,
                "current_street": self.current_street,
                "current_area": self.current_area,
                "current_village_town": self.current_village_town,
                "current_city": self.current_city,
                "current_district": self.current_district,
                "current_state": self.current_state,
                "current_pincode": self.current_pincode,
            }
            missing = [name for name, value in required_current_fields.items() if not value]
            if missing:
                raise ValidationError(
                    "Current address is required in full when it differs from the "
                    "permanent address."
                )

    def save(self, *args, **kwargs):
        if not self.customer_id:
            self.customer_id = CustomerIDCounter.next_customer_id()
        if self.same_as_permanent_address:
            self.current_door_no = self.permanent_door_no
            self.current_street = self.permanent_street
            self.current_area = self.permanent_area
            self.current_village_town = self.permanent_village_town
            self.current_city = self.permanent_city
            self.current_district = self.permanent_district
            self.current_state = self.permanent_state
            self.current_pincode = self.permanent_pincode
        super().save(*args, **kwargs)

    @property
    def has_verified_kyc(self):
        return self.documents.filter(verified_status="verified").exists()


class CustomerReference(models.Model):
    """A customer may have more than one reference/family contact."""

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="references"
    )
    reference_name = models.CharField(max_length=150)
    reference_mobile = models.CharField(max_length=10, validators=[mobile_validator])
    reference_address = models.TextField()
    relationship = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.reference_name} ({self.relationship}) for {self.customer}"


class CustomerBankDetail(models.Model):
    ACCOUNT_SAVINGS = "savings"
    ACCOUNT_CURRENT = "current"
    ACCOUNT_TYPE_CHOICES = [
        (ACCOUNT_SAVINGS, "Savings"),
        (ACCOUNT_CURRENT, "Current"),
    ]

    customer = models.OneToOneField(
        Customer, on_delete=models.CASCADE, related_name="bank_detail"
    )
    account_holder_name = models.CharField(max_length=150)
    bank_name = models.CharField(max_length=150)
    branch = models.CharField(max_length=150)
    account_number = models.CharField(max_length=30)
    ifsc = models.CharField(max_length=11, validators=[ifsc_validator])
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPE_CHOICES)

    def masked_account_number(self):
        """Used everywhere except the single edit form, per the spec's
        rule against exposing full account numbers on list/summary pages."""
        if len(self.account_number) <= 4:
            return self.account_number
        return "X" * (len(self.account_number) - 4) + self.account_number[-4:]

    def __str__(self):
        return f"{self.bank_name} — {self.masked_account_number()}"
