from decimal import Decimal

from django.core.validators import RegexValidator
from django.db import models, transaction
from django.utils import timezone

mobile_validator = RegexValidator(
    regex=r"^[6-9]\d{9}$",
    message="Enter a valid 10-digit mobile number.",
)


class InvestorIDCounter(models.Model):
    """Same local-counter pattern used across the other apps."""
    last_number = models.PositiveIntegerField(default=0)

    @classmethod
    def next_investor_id(cls):
        from core.models import get_setting

        with transaction.atomic():
            counter, _ = cls.objects.select_for_update().get_or_create(pk=1)
            counter.last_number += 1
            counter.save(update_fields=["last_number"])
            padding = int(get_setting("id_number_padding", "6"))
            return f"INV-{counter.last_number:0{padding}d}"


class Investor(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_INACTIVE = "inactive"
    STATUS_CHOICES = [(STATUS_ACTIVE, "Active"), (STATUS_INACTIVE, "Inactive")]

    investor_id = models.CharField(max_length=20, unique=True, editable=False)
    full_name = models.CharField(max_length=150)
    mobile = models.CharField(max_length=10, validators=[mobile_validator])
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.investor_id:
            self.investor_id = InvestorIDCounter.next_investor_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.investor_id} — {self.full_name}"

    @property
    def total_deposited(self):
        """Sum of this investor's deposit entries — each one already
        reflects its CURRENT (possibly corrected) amount, since
        edit_deposit() updates the deposit row itself in place. Deliberately
        excludes 'adjustment' entries: those exist only to correct the
        pool's running balance, and including them here would double-count
        a correction that's already reflected in the deposit's own amount."""
        return self.ledger_entries.filter(
            entry_type=InvestmentLedgerEntry.TYPE_DEPOSIT
        ).aggregate(total=models.Sum("amount"))["total"] or Decimal("0")


class InvestmentPoolBalance(models.Model):
    """Singleton row holding the current available pool balance — kept
    as a running total (not recomputed by summing every ledger entry on
    every page load) and updated atomically alongside each new entry,
    same pattern as the ID counters above."""
    current_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))

    @classmethod
    def get_balance(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj.current_balance


class InvestmentLedgerEntry(models.Model):
    """The 'Invest Log' — one append-only row per event that changes the
    available pool: a deposit (+), a loan being disbursed (-), a
    repayment coming back in (+), or a correction when a payment's
    amount is later edited (+/-). balance_after is the running pool
    total immediately after this entry, so the log reads like a bank
    passbook without recomputing a sum on every view."""

    TYPE_DEPOSIT = "deposit"
    TYPE_LOAN_DISBURSED = "loan_disbursed"
    TYPE_REPAYMENT = "repayment"
    TYPE_ADJUSTMENT = "adjustment"
    TYPE_CHOICES = [
        (TYPE_DEPOSIT, "Investor Deposit"),
        (TYPE_LOAN_DISBURSED, "Loan Disbursed"),
        (TYPE_REPAYMENT, "Repayment Received"),
        (TYPE_ADJUSTMENT, "Adjustment"),
    ]

    entry_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    investor = models.ForeignKey(
        Investor, null=True, blank=True, on_delete=models.PROTECT, related_name="ledger_entries"
    )
    loan = models.ForeignKey(
        "loans.Loan", null=True, blank=True, on_delete=models.SET_NULL, related_name="investment_entries"
    )
    payment = models.ForeignKey(
        "payments.Payment", null=True, blank=True, on_delete=models.SET_NULL, related_name="investment_entries"
    )
    amount = models.DecimalField(
        max_digits=14, decimal_places=2,
        help_text="Signed: positive adds to the pool, negative reduces it.",
    )
    balance_after = models.DecimalField(max_digits=14, decimal_places=2, editable=False)
    previous_amount = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Set only if this entry was later edited — what it was before.",
    )
    edited_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.get_entry_type_display()}: {self.amount}"

    @property
    def added_amount(self):
        return self.amount if self.amount > 0 else None

    @property
    def reduced_amount(self):
        return -self.amount if self.amount < 0 else None


def record_ledger_entry(entry_type, amount, investor=None, loan=None, payment=None, notes=""):
    """The single, atomic way any code adds a ledger entry — updates the
    pool balance and the entry's balance_after together, so the two can
    never drift apart even under concurrent writes."""
    with transaction.atomic():
        pool, _ = InvestmentPoolBalance.objects.select_for_update().get_or_create(pk=1)
        pool.current_balance += amount
        pool.save(update_fields=["current_balance"])
        return InvestmentLedgerEntry.objects.create(
            entry_type=entry_type, investor=investor, loan=loan, payment=payment,
            amount=amount, balance_after=pool.current_balance, notes=notes,
        )


def edit_deposit(entry, new_amount):
    """Corrects an existing deposit entry. The entry's own `amount`
    field is updated in place (with previous_amount/edited_at kept for
    reference, same pattern as Payment edits) so it always shows the
    current correct figure — and a separate, visible 'adjustment' entry
    is recorded for the difference, which is what actually keeps the
    pool balance and every later balance_after correct without having
    to rewrite any other historical row."""
    if entry.entry_type != InvestmentLedgerEntry.TYPE_DEPOSIT:
        raise ValueError("Only deposit entries can be edited this way.")

    old_amount = entry.amount
    delta = new_amount - old_amount
    if delta == 0:
        return entry, None

    with transaction.atomic():
        entry.previous_amount = old_amount
        entry.edited_at = timezone.now()
        entry.amount = new_amount
        entry.save(update_fields=["amount", "previous_amount", "edited_at"])

        adjustment = record_ledger_entry(
            InvestmentLedgerEntry.TYPE_ADJUSTMENT, amount=delta, investor=entry.investor,
            notes=(
                f"Correction to deposit from {entry.created_at.date()}: "
                f"Rs. {old_amount} -> Rs. {new_amount}"
            ),
        )
    return entry, adjustment
