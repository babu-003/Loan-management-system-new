from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction


class LoanIDCounter(models.Model):
    """Same pattern as customers.CustomerIDCounter — local to this app so
    the loans module stays a self-contained, deletable unit."""
    last_number = models.PositiveIntegerField(default=0)

    @classmethod
    def next_loan_number(cls):
        with transaction.atomic():
            counter, _ = cls.objects.select_for_update().get_or_create(pk=1)
            counter.last_number += 1
            counter.save(update_fields=["last_number"])
            return f"LN-{counter.last_number:06d}"


class GroupIDCounter(models.Model):
    last_number = models.PositiveIntegerField(default=0)

    @classmethod
    def next_group_id(cls):
        with transaction.atomic():
            counter, _ = cls.objects.select_for_update().get_or_create(pk=1)
            counter.last_number += 1
            counter.save(update_fields=["last_number"])
            return f"GRP-{counter.last_number:06d}"


class LoanType(models.Model):
    """Admin-configurable, e.g. Personal Loan, Business Loan, Gold Loan."""
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class InterestType(models.Model):
    """Admin-configurable list of interest methods. calculation_method
    drives which formula the engine uses — new methods can be added later
    (e.g. Reducing Balance) without any change to the Loan model."""
    METHOD_FLAT = "flat"
    METHOD_CHOICES = [
        (METHOD_FLAT, "Flat Interest"),
        # Reducing Balance can be added here later — Loan.interest_type
        # already points at this table, so no Loan schema change needed.
    ]

    name = models.CharField(max_length=100)
    calculation_method = models.CharField(max_length=20, choices=METHOD_CHOICES, default=METHOD_FLAT)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class LoanGroup(models.Model):
    """Grouping/reporting construct only. Deliberately holds no financial
    fields — every total shown for a group is aggregated live from its
    Loan rows, so it can never drift out of sync (see the DB design doc,
    §3 'LoanGroup'). Each member customer keeps a fully independent
    Customer + Loan record; this table never touches customers.Customer."""

    STATUS_ACTIVE = "active"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [(STATUS_ACTIVE, "Active"), (STATUS_CLOSED, "Closed")]

    group_id = models.CharField(max_length=20, unique=True, editable=False)
    group_name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.group_id:
            self.group_id = GroupIDCounter.next_group_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.group_id} — {self.group_name}"

    @property
    def total_principal(self):
        return self.loans.aggregate(total=models.Sum("principal_amount"))["total"] or Decimal("0")

    @property
    def total_payable(self):
        return self.loans.aggregate(total=models.Sum("total_payable"))["total"] or Decimal("0")

    @property
    def total_paid(self):
        total = Decimal("0")
        for loan in self.loans.all():
            total += loan.total_paid
        return total

    @property
    def total_outstanding(self):
        return self.total_payable - self.total_paid

    @property
    def member_count(self):
        return self.loans.values("customer").distinct().count()


# --- Flat-interest engine defaults (documented, not silently assumed) ---
# Interval, in days, used ONLY to convert "number of installments" into a
# duration for the flat-interest formula. This is a stated assumption —
# tell me if your business uses a different day-count convention (e.g.
# exact calendar months instead of a flat 30 days) and I'll adjust it.
FREQUENCY_INTERVAL_DAYS = {
    "daily": 1,
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
    # "custom" has no fixed entry — Loan.custom_interval_days is used instead.
}


class Loan(models.Model):
    FREQUENCY_DAILY = "daily"
    FREQUENCY_WEEKLY = "weekly"
    FREQUENCY_BIWEEKLY = "biweekly"
    FREQUENCY_MONTHLY = "monthly"
    FREQUENCY_CUSTOM = "custom"
    FREQUENCY_CHOICES = [
        (FREQUENCY_DAILY, "Daily"),
        (FREQUENCY_WEEKLY, "Weekly"),
        (FREQUENCY_BIWEEKLY, "Biweekly"),
        (FREQUENCY_MONTHLY, "Monthly"),
        (FREQUENCY_CUSTOM, "Custom interval"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_COMPLETED = "completed"
    STATUS_CLOSED = "closed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CLOSED, "Closed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    loan_number = models.CharField(max_length=20, unique=True, editable=False)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="loans"
    )
    loan_group = models.ForeignKey(
        LoanGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="loans"
    )
    loan_type = models.ForeignKey(LoanType, on_delete=models.PROTECT)
    interest_type = models.ForeignKey(InterestType, on_delete=models.PROTECT)

    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, help_text="Annual interest rate, %."
    )
    start_date = models.DateField()

    repayment_frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES)
    custom_interval_days = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Only used when Repayment Frequency = Custom interval.",
    )
    number_of_installments = models.PositiveIntegerField()
    first_due_date = models.DateField()

    purpose = models.CharField(max_length=255, blank=True)
    remarks = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    total_interest = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    total_payable = models.DecimalField(max_digits=12, decimal_places=2, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    closing_date = models.DateField(null=True, blank=True)
    closing_remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.loan_number} — {self.customer.full_name}"

    def clean(self):
        if self.repayment_frequency == self.FREQUENCY_CUSTOM and not self.custom_interval_days:
            raise ValidationError(
                "Custom interval (in days) is required when Repayment Frequency is Custom."
            )

    def _interval_days(self):
        if self.repayment_frequency == self.FREQUENCY_CUSTOM:
            return self.custom_interval_days
        return FREQUENCY_INTERVAL_DAYS[self.repayment_frequency]

    def calculate_flat_interest(self):
        """Interest = Principal × Rate% × Duration(years).
        Duration is derived from number_of_installments × interval_days,
        per FREQUENCY_INTERVAL_DAYS above — a stated assumption, not a
        silent guess."""
        duration_days = self.number_of_installments * self._interval_days()
        duration_years = Decimal(duration_days) / Decimal("365")
        interest = (self.principal_amount * self.interest_rate / Decimal("100")) * duration_years
        return interest.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    def compute_totals(self):
        """Populates total_interest / total_payable. Currently only Flat
        is implemented — if interest_type.calculation_method is anything
        else, this raises rather than silently producing a wrong number."""
        if self.interest_type.calculation_method != InterestType.METHOD_FLAT:
            raise NotImplementedError(
                f"No calculation engine implemented yet for "
                f"'{self.interest_type.calculation_method}'."
            )
        self.total_interest = self.calculate_flat_interest()
        self.total_payable = self.principal_amount + self.total_interest

    def generate_installment_schedule(self):
        """Creates N equal installments. Any rupee left over from rounding
        is added to the LAST installment so the sum always exactly equals
        total_payable — never silently drops a rupee."""
        from datetime import timedelta

        base_amount = (self.total_payable / self.number_of_installments).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
        allocated = base_amount * (self.number_of_installments - 1)
        last_amount = self.total_payable - allocated

        interval = self._interval_days()
        installments = []
        for index in range(self.number_of_installments):
            due_date = self.first_due_date + timedelta(days=interval * index)
            amount = base_amount if index < self.number_of_installments - 1 else last_amount
            installments.append(
                Installment(
                    loan=self,
                    installment_number=index + 1,
                    due_date=due_date,
                    original_due_date=due_date,
                    due_amount=amount,
                )
            )
        Installment.objects.bulk_create(installments)

    @property
    def total_paid(self):
        return self.installments.aggregate(total=models.Sum("paid_amount"))["total"] or Decimal("0")

    @property
    def total_outstanding(self):
        return self.total_payable - self.total_paid


class Installment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PARTIALLY_PAID = "partially_paid"
    STATUS_PAID = "paid"
    STATUS_OVERDUE = "overdue"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PARTIALLY_PAID, "Partially Paid"),
        (STATUS_PAID, "Paid"),
        (STATUS_OVERDUE, "Overdue"),
    ]

    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="installments")
    installment_number = models.PositiveIntegerField()
    due_date = models.DateField()
    original_due_date = models.DateField(
        help_text="What the schedule originally generated — kept even if due_date is edited."
    )
    due_amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_PENDING)

    class Meta:
        ordering = ["installment_number"]
        unique_together = ["loan", "installment_number"]

    def __str__(self):
        return f"{self.loan.loan_number} — Installment {self.installment_number}"

    @property
    def balance_amount(self):
        return self.due_amount - self.paid_amount

    @property
    def is_overdue(self):
        from django.utils import timezone
        return self.status != self.STATUS_PAID and self.due_date < timezone.localdate()
