from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction


class LoanIDCounter(models.Model):
    """Same pattern as customers.CustomerIDCounter — local to this app so
    the loans module stays a self-contained, deletable unit."""
    last_number = models.PositiveIntegerField(default=0)

    @classmethod
    def next_loan_number(cls):
        from core.models import get_setting
        prefix = get_setting("loan_id_prefix", "LN")
        padding = int(get_setting("id_number_padding", "6"))
        with transaction.atomic():
            counter, _ = cls.objects.select_for_update().get_or_create(pk=1)
            counter.last_number += 1
            counter.save(update_fields=["last_number"])
            return f"{prefix}-{counter.last_number:0{padding}d}"


class GroupIDCounter(models.Model):
    last_number = models.PositiveIntegerField(default=0)

    @classmethod
    def next_group_id(cls):
        from core.models import get_setting
        prefix = get_setting("group_id_prefix", "GRP")
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
    drives which formula the engine uses. Admin selects Flat Interest,
    Reducing Balance, or Fixed Interest when creating a loan."""
    METHOD_FLAT = "flat"
    METHOD_REDUCING = "reducing"
    METHOD_FIXED = "fixed"
    METHOD_CHOICES = [
        (METHOD_FLAT, "Flat Interest"),
        (METHOD_REDUCING, "Reducing Balance"),
        (METHOD_FIXED, "Fixed Interest"),
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
        return self.members.count()


class LoanGroupMember(models.Model):
    """Explicit membership in a loan group.

    A customer can belong to at most one group, and membership is created
    before the member receives a loan. This keeps group membership separate
    from the member's loan record.
    """

    group = models.ForeignKey(
        LoanGroup, on_delete=models.CASCADE, related_name="members"
    )
    customer = models.OneToOneField(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="loan_group_membership",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["joined_at", "id"]

    def __str__(self):
        return f"{self.group.group_id} — {self.customer.full_name}"


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
    assigned_staff = models.ForeignKey(
        "staff.Staff", on_delete=models.SET_NULL, null=True, blank=True, related_name="loans",
        help_text="Staff member responsible for collecting this loan.",
    )
    penalty_per_day = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        help_text="Penalty charged for each day an installment remains overdue.",
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

        if self.loan_group_id and self.customer_id:
            membership = LoanGroupMember.objects.filter(customer_id=self.customer_id).first()
            if not membership:
                raise ValidationError({
                    "customer": "Customer must be added to this group before creating a group loan."
                })
            if membership.group_id != self.loan_group_id:
                raise ValidationError({
                    "customer": "This customer belongs to a different loan group."
                })

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
        elif method == InterestType.METHOD_FIXED:
            # For this method, 1.6 means 1.6 × 100 = 160 currency units
            # of interest on EVERY installment; it is not a percentage.
            self.total_interest = (self.interest_rate * Decimal("100") * self.number_of_installments).quantize(Decimal("0.01"))
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

    def _flat_schedule_rows(self):
        """Equal installments summing exactly to total_payable /
        total_interest, with any rounding remainder on the LAST
        installment. Requires total_payable/total_interest to already be
        set (compute_totals() must run first). Shared by
        generate_installment_schedule() and the standalone Loan
        Calculator, so both always agree — never a separate copy of the
        same rounding logic that could drift out of sync."""
        n = self.number_of_installments
        base_amount = (self.total_payable / n).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        last_amount = self.total_payable - base_amount * (n - 1)
        base_interest = (self.total_interest / n).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        last_interest = self.total_interest - base_interest * (n - 1)

        rows = []
        for index in range(n):
            is_last = index == n - 1
            amount = last_amount if is_last else base_amount
            interest_component = last_interest if is_last else base_interest
            rows.append((amount - interest_component, interest_component, amount))
        return rows

    def _fixed_interest_schedule_rows(self):
        """Return installments with the full fixed interest amount on each
        row. Only principal is divided across installments; interest is
        never split or redistributed."""
        n = self.number_of_installments
        fixed_interest = (self.interest_rate * Decimal("100")).quantize(Decimal("0.01"))
        base_principal = (self.principal_amount / n).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        rows = []
        principal_remaining = self.principal_amount
        for index in range(n):
            principal_component = (
                principal_remaining if index == n - 1 else base_principal
            )
            amount = principal_component + fixed_interest
            rows.append((principal_component, fixed_interest, amount))
            principal_remaining -= principal_component
        return rows

    def generate_installment_schedule(self):
        """Creates N installments using the selected interest method."""
        method = self.interest_type.calculation_method
        installments = []

        if method == InterestType.METHOD_REDUCING:
            rows, _ = self._reducing_balance_schedule()
        elif method == InterestType.METHOD_FIXED:
            rows = self._fixed_interest_schedule_rows()
        else:
            rows = self._flat_schedule_rows()

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

        Installment.objects.bulk_create(installments)

    @property
    def total_paid(self):
        return self.installments.aggregate(total=models.Sum("paid_amount"))["total"] or Decimal("0")

    @property
    def total_outstanding(self):
        # Dynamic outstanding includes any penalty that has accrued on
        # currently overdue installments. The scheduled total_payable
        # remains unchanged because penalties are conditional charges.
        return sum(
            (installment.balance_amount for installment in self.installments.all()),
            Decimal("0"),
        )


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

    def penalty_amount(self, as_of_date=None):
        """Current penalty for this installment. Penalty starts the day
        after the due date and is charged per overdue day. A paid
        installment stops accruing penalty."""
        from django.utils import timezone

        if self.status == self.STATUS_PAID:
            return Decimal("0.00")
        if as_of_date is None:
            as_of_date = timezone.localdate()
        if as_of_date <= self.due_date:
            return Decimal("0.00")
        overdue_days = (as_of_date - self.due_date).days
        return (self.loan.penalty_per_day * overdue_days).quantize(Decimal("0.01"))

    def total_due_amount(self, as_of_date=None):
        return self.due_amount + self.penalty_amount(as_of_date)

    def balance_amount_as_of(self, as_of_date=None):
        balance = self.total_due_amount(as_of_date) - self.paid_amount
        return max(balance, Decimal("0.00"))

    @property
    def balance_amount(self):
        return self.balance_amount_as_of()

    @property
    def is_overdue(self):
        from django.utils import timezone
        return self.status != self.STATUS_PAID and self.due_date < timezone.localdate()
