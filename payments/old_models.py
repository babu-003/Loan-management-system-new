from decimal import Decimal

from django.db import models, transaction

from loans.models import Installment, Loan


class PaymentIDCounter(models.Model):
    """Same local-counter pattern as the other apps — keeps payments a
    self-contained, deletable unit."""
    last_number = models.PositiveIntegerField(default=0)

    @classmethod
    def next_receipt_number(cls):     # (or next_loan_number / next_group_id / next_receipt_number)
        from core.models import get_setting
        prefix = get_setting("receipt_id_prefix", "REC")   # matching key per file, see below
        padding = int(get_setting("id_number_padding", "6"))
        with transaction.atomic():
            counter, _ = cls.objects.select_for_update().get_or_create(pk=1)
            counter.last_number += 1
            counter.save(update_fields=["last_number"])
            return f"{prefix}-{counter.last_number:0{padding}d}"


class Payment(models.Model):
    """One receipt. amount_paid is whatever is CURRENTLY correct — if
    edited, previous_amount/edited_at record what it was before, per your
    choice to keep the prior value visible rather than a full history."""

    receipt_number = models.CharField(max_length=20, unique=True, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.PROTECT, related_name="payments")
    payment_date = models.DateField()
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    previous_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    unallocated_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0"),
        help_text="Left over if this payment exceeds everything currently owed on the loan.",
    )
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]

    def __str__(self):
        return f"{self.receipt_number} — {self.loan.loan_number} — ₹{self.amount_paid}"


class PaymentAllocation(models.Model):
    """How one payment was split across installments. Kept as its own
    table (not a single FK on Payment) specifically so a payment CAN
    cover more than one installment, and so editing a payment can be
    reversed and cleanly reapplied without guesswork."""

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="allocations")
    installment = models.ForeignKey(Installment, on_delete=models.CASCADE, related_name="allocations")
    amount_allocated = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.payment.receipt_number} → Installment {self.installment.installment_number}: ₹{self.amount_allocated}"


def _recompute_installment_status(installment):
    if installment.paid_amount <= 0:
        installment.status = Installment.STATUS_PENDING
    elif installment.paid_amount < installment.due_amount:
        installment.status = Installment.STATUS_PARTIALLY_PAID
    else:
        installment.status = Installment.STATUS_PAID
    installment.save(update_fields=["paid_amount", "status"])


def _sync_loan_status(loan):
    """Flips a loan to Completed once fully paid, and back to Active if
    an edit later reduces payments below the full amount again."""
    if loan.total_outstanding <= 0 and loan.status == Loan.STATUS_ACTIVE:
        loan.status = Loan.STATUS_COMPLETED
        loan.save(update_fields=["status"])
    elif loan.total_outstanding > 0 and loan.status == Loan.STATUS_COMPLETED:
        loan.status = Loan.STATUS_ACTIVE
        loan.save(update_fields=["status"])


@transaction.atomic
def allocate_payment(payment):
    """Applies payment.amount_paid across the loan's installments,
    OLDEST installment_number first. Any amount left over after every
    installment is fully covered cascades forward automatically — this
    is what makes an overpayment reduce the NEXT installment's balance,
    per your answer. If it overflows past the very last installment
    (the loan is already fully paid), the remainder is recorded as
    Payment.unallocated_amount rather than silently discarded."""
    remaining = payment.amount_paid
    installments = payment.loan.installments.filter(
        status__in=[Installment.STATUS_PENDING, Installment.STATUS_PARTIALLY_PAID, Installment.STATUS_OVERDUE]
    ).order_by("installment_number")

    for installment in installments:
        if remaining <= 0:
            break
        balance = installment.balance_amount
        if balance <= 0:
            continue
        applied = min(remaining, balance)
        PaymentAllocation.objects.create(payment=payment, installment=installment, amount_allocated=applied)
        installment.paid_amount += applied
        _recompute_installment_status(installment)
        remaining -= applied

    payment.unallocated_amount = remaining
    payment.save(update_fields=["unallocated_amount"])
    _sync_loan_status(payment.loan)


@transaction.atomic
def reverse_payment_allocations(payment):
    """Undoes exactly this payment's contribution to each installment it
    touched — used before re-applying an edited amount. Only subtracts
    what THIS payment added, so other payments' allocations are untouched."""
    for allocation in payment.allocations.select_related("installment"):
        installment = allocation.installment
        installment.paid_amount -= allocation.amount_allocated
        if installment.paid_amount < 0:
            installment.paid_amount = Decimal("0")
        _recompute_installment_status(installment)
    payment.allocations.all().delete()
    payment.unallocated_amount = Decimal("0")
    payment.save(update_fields=["unallocated_amount"])
    _sync_loan_status(payment.loan)
