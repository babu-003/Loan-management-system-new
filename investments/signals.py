from django.db.models.signals import post_save, pre_save

from .models import InvestmentLedgerEntry, record_ledger_entry


def _capture_old_payment_amount(sender, instance, **kwargs):
    """Same pre_save-snapshot technique as core.signals — needed to
    detect an edited payment amount so the pool can be corrected by
    exactly the difference, not the whole new amount again."""
    if instance.pk:
        try:
            instance._investments_old_amount = sender.objects.get(pk=instance.pk).amount_paid
        except sender.DoesNotExist:
            instance._investments_old_amount = None
    else:
        instance._investments_old_amount = None


def _on_loan_saved(sender, instance, created, **kwargs):
    if not created:
        return  # only the initial disbursement affects the pool
    record_ledger_entry(
        InvestmentLedgerEntry.TYPE_LOAN_DISBURSED,
        amount=-instance.principal_amount,
        loan=instance,
        notes=f"Principal disbursed for loan {instance.loan_number}",
    )


def _on_payment_saved(sender, instance, created, **kwargs):
    if created:
        record_ledger_entry(
            InvestmentLedgerEntry.TYPE_REPAYMENT,
            amount=instance.amount_paid,
            payment=instance,
            notes=f"Repayment received for loan {instance.loan.loan_number}",
        )
        return

    old_amount = getattr(instance, "_investments_old_amount", None)
    if old_amount is None or old_amount == instance.amount_paid:
        return  # nothing changed, or we couldn't tell — don't guess

    delta = instance.amount_paid - old_amount
    record_ledger_entry(
        InvestmentLedgerEntry.TYPE_ADJUSTMENT,
        amount=delta,
        payment=instance,
        notes=f"Payment {instance.receipt_number} amount edited: {old_amount} -> {instance.amount_paid}",
    )


def register():
    from loans.models import Loan
    from payments.models import Payment

    post_save.connect(_on_loan_saved, sender=Loan, weak=False)
    pre_save.connect(_capture_old_payment_amount, sender=Payment, weak=False)
    post_save.connect(_on_payment_saved, sender=Payment, weak=False)
