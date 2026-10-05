from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction


class LoanIDCounter(models.Model):
    """Same pattern as customers.CustomerIDCounter — local to this app so
    the loans module stays a self-contained, deletable unit."""
    last_number = models.PositiveIntegerField(default=0)

    @classmethod
    def next_loan_number(cls):     # (or next_loan_number / next_group_id / next_receipt_number)
        from core.models import get_setting
        prefix = get_setting("loan_id_prefix", "LN")   # matching key per file, see below
        padding = int(get_setting("id_number_padding", "6"))
        with transaction.atomic():
            counter, _ = cls.objects.select_for_update().get_or_create(pk=1)
            counter.last_number += 1
            counter.save(update_fields=["last_number"])
            return f"{prefix}-{counter.last_number:0{padding}d}"


class GroupIDCounter(models.Model):
    last_number = models.PositiveIntegerField(default=0)

    @classmethod
    def next_group_id(cls):     # (or next_loan_number / next_group_id / next_receipt_number)
        from core.models import get_setting
        prefix = get_setting("group_id_prefix", "GRP")   # matching key per file, see below
        padding = int(get_setting("id_number_padding", "6"))
        with transaction.atomic():
            counter, _ = cls.objects.select_for_update().get_or_create(pk=1)
            counter.last_number += 1
            counter.save(update_fields=["last_number"])
            return f"{prefix}-{counter.last_number:0{padding}d}"


class LoanType(models.Model):
    """Admin-configurable, e.g. Personal Loan, Business Loan, Gold Loan."""
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class InterestType(models.Model):
    """Admin-configurable list of interest methods. calculation_method
    drives which formula the engine uses. Admin picks Flat or Reducing
    Balance per loan by choosing an InterestType row when creating it."""
    METHOD_FLAT = "flat"
    METHOD_REDUCING = "reducing"
    METHOD_CHOICES = [
        (METHOD_FLAT, "Flat Interest"),
        (METHOD_REDUCING, "Reducing Balance"),
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


# Day-step used only for generating due DATES on non-monthly frequencies
# (daily/weekly/biweekly/custom). Monthly is handled separately using real
# calendar months, not a day count — see _add_calendar_months() below.
FREQUENCY_INTERVAL_DAYS = {
    "daily": 1,
    "weekly": 7,
    "biweekly": 14,
    # "custom" has no fixed entry — Loan.custom_interval_days is used instead.
}


def _add_calendar_months(source_date, months):
    """Steps a date forward by exact calendar months (31 Jan + 1 month =
    28/29 Feb, not 'Jan 31 + 30 days'). This is what makes monthly
    installments land on the same date every month instead of drifting,
    and what makes 12 monthly installments = exactly 1.0 year for
    interest math, instead of 360/365 of a year."""
    import calendar

    month_index = source_date.month - 1 + months
    year = source_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(source_date.day, calendar.monthrange(year, month)[1])
    return source_date.replace(year=year, month=month, day=day)


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

    def _periods_per_year(self):
        """Exact periods/year per frequency — this is what fixes the
        360-vs-365 mismatch. Monthly is exactly 12 (not a 30-day-step
        approximation); every other frequency is 365 / its day interval."""
        if self.repayment_frequency == self.FREQUENCY_MONTHLY:
            return Decimal("12")
        if self.repayment_frequency == self.FREQUENCY_CUSTOM:
            return Decimal("365") / Decimal(self.custom_interval_days)
        return Decimal("365") / Decimal(FREQUENCY_INTERVAL_DAYS[self.repayment_frequency])

    def _due_date_for_index(self, index):
        if self.repayment_frequency == self.FREQUENCY_MONTHLY:
            return _add_calendar_months(self.first_due_date, index)
        interval = (
            self.custom_interval_days
            if self.repayment_frequency == self.FREQUENCY_CUSTOM
            else FREQUENCY_INTERVAL_DAYS[self.repayment_frequency]
        )
        from datetime import timedelta
        return self.first_due_date + timedelta(days=interval * index)

    def calculate_flat_interest(self):
        """Interest = Principal × Rate% × Duration(years), where
        Duration = number_of_installments / periods_per_year — e.g. 12
        monthly installments = exactly 1.0 year, not 360/365 ≈ 0.986."""
        duration_years = Decimal(self.number_of_installments) / self._periods_per_year()
        interest = (self.principal_amount * self.interest_rate / Decimal("100")) * duration_years
        return interest.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    def compute_totals(self):
        """Populates total_interest / total_payable for either method."""
        method = self.interest_type.calculation_method
        if method == InterestType.METHOD_FLAT:
            self.total_interest = self.calculate_flat_interest()
            self.total_payable = self.principal_amount + self.total_interest
        elif method == InterestType.METHOD_REDUCING:
            _, total_interest = self._reducing_balance_schedule()
            self.total_interest = total_interest
            self.total_payable = self.principal_amount + self.total_interest
        else:
            raise NotImplementedError(f"No calculation engine implemented for '{method}'.")

    def _reducing_balance_schedule(self):
        """Standard EMI amortization: interest is charged on the
        OUTSTANDING balance each period, not the original principal.
        Returns (rows, total_interest) where each row is
        (principal_component, interest_component, installment_amount).
        The last installment absorbs any rounding remainder so the
        outstanding balance always reaches exactly zero."""
        n = self.number_of_installments
        r = (self.interest_rate / Decimal("100")) / self._periods_per_year()
        principal = self.principal_amount

        if r == 0:
            emi = (principal / n).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        else:
            factor = (1 + r) ** n
            emi = (principal * r * factor / (factor - 1)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )

        rows = []
        balance = principal
        total_interest = Decimal("0")
        for index in range(n):
            interest_component = (balance * r).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            if index == n - 1:
                principal_component = balance  # clears exactly to zero
                amount = principal_component + interest_component
            else:
                principal_component = emi - interest_component
                amount = emi
            balance -= principal_component
            total_interest += interest_component
            rows.append((principal_component, interest_component, amount))
        return rows, total_interest

    def generate_installment_schedule(self):
        """Creates N installments, either equal (Flat) or amortizing
        (Reducing Balance). Both get a principal/interest split stored
        per row for consistent display."""
        method = self.interest_type.calculation_method
        installments = []

        if method == InterestType.METHOD_REDUCING:
            rows, _ = self._reducing_balance_schedule()
            for index, (principal_component, interest_component, amount) in enumerate(rows):
                due_date = self._due_date_for_index(index)
                installments.append(
                    Installment(
                        loan=self, installment_number=index + 1,
                        due_date=due_date, original_due_date=due_date,
                        due_amount=amount,
                        principal_component=principal_component,
                        interest_component=interest_component,
                    )
                )
        else:
            n = self.number_of_installments
            base_amount = (self.total_payable / n).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            last_amount = self.total_payable - base_amount * (n - 1)
            base_interest = (self.total_interest / n).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            last_interest = self.total_interest - base_interest * (n - 1)

            for index in range(n):
                due_date = self._due_date_for_index(index)
                is_last = index == n - 1
                amount = last_amount if is_last else base_amount
                interest_component = last_interest if is_last else base_interest
                installments.append(
                    Installment(
                        loan=self, installment_number=index + 1,
                        due_date=due_date, original_due_date=due_date,
                        due_amount=amount,
                        principal_component=amount - interest_component,
                        interest_component=interest_component,
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
    principal_component = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    interest_component = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
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
