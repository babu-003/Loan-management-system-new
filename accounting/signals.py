from decimal import Decimal

from django.db import transaction
from django.db.models.signals import (
    post_save,
    pre_save,
)

from .models import (
    LedgerAccount,
    Voucher,
    VoucherEntry,
    create_balanced_voucher,
    create_voucher,
    get_bank_account,
    get_cash_account,
    get_customer_account,
    get_or_create_named_account,
)


def _money_account(mode):

    if mode in {
        Voucher.MODE_ONLINE,
        Voucher.MODE_UPI,
        Voucher.MODE_CHEQUE,
    }:
        return get_bank_account()

    return get_cash_account()


def _capture_old_payment(
    sender,
    instance,
    **kwargs
):

    if not instance.pk:

        instance._accounting_old = None

        return

    try:

        old = sender.objects.get(
            pk=instance.pk
        )

        instance._accounting_old = (
            old.amount_paid,
            old.payment_mode,
            old.transaction_id,
            old.payment_date,
        )

    except sender.DoesNotExist:

        instance._accounting_old = None


def _loan_created(
    sender,
    instance,
    created,
    **kwargs
):

    if not created:
        return

    customer_account = (
        get_customer_account(
            instance.customer
        )
    )

    cash = get_cash_account()

    create_voucher(
        voucher_type=Voucher.TYPE_PAYMENT,
        amount=instance.principal_amount,
        debit_account=customer_account,
        credit_account=cash,
        party_name=instance.customer.full_name,
        narration=(
            f"Loan disbursement for "
            f"{instance.loan_number}"
        ),
        source_type="loan",
        source_id=str(instance.pk),
    )


def _component_split(payment):

    principal_total = Decimal("0")
    interest_total = Decimal("0")
    penalty_total = Decimal("0")

    for allocation in (
        payment.allocations
        .select_related("installment")
        .order_by(
            "installment__installment_number",
            "id"
        )
    ):

        installment = allocation.installment

        previous_paid = sum(
            (
                other.amount_allocated
                for other in (
                    installment.allocations
                    .exclude(
                        payment_id=payment.pk
                    )
                )
            ),
            Decimal("0")
        )

        principal_remaining = max(
            installment.principal_component
            - min(
                previous_paid,
                installment.principal_component
            ),
            Decimal("0")
        )

        interest_paid_before = max(
            previous_paid
            - installment.principal_component,
            Decimal("0")
        )

        interest_remaining = max(
            installment.interest_component
            - min(
                interest_paid_before,
                installment.interest_component
            ),
            Decimal("0")
        )

        penalty_paid_before = max(
            previous_paid
            - installment.principal_component
            - installment.interest_component,
            Decimal("0")
        )

        penalty_total_due = (
            installment.penalty_amount(
                payment.payment_date
            )
        )

        penalty_remaining = max(
            penalty_total_due
            - penalty_paid_before,
            Decimal("0")
        )

        remaining = allocation.amount_allocated

        part = min(
            remaining,
            principal_remaining
        )

        principal_total += part

        remaining -= part

        part = min(
            remaining,
            interest_remaining
        )

        interest_total += part

        remaining -= part

        part = min(
            remaining,
            penalty_remaining
        )

        penalty_total += part

        remaining -= part

        if remaining > 0:

            principal_total += remaining

    return (
        principal_total,
        interest_total,
        penalty_total
    )


def _post_payment_accounting(
    payment_id,
    old=None
):

    from payments.models import Payment

    payment = (
        Payment.objects
        .select_related(
            "loan__customer"
        )
        .get(pk=payment_id)
    )

    money = _money_account(
        payment.payment_mode
    )

    customer_account = (
        get_customer_account(
            payment.loan.customer
        )
    )

    if old:

        (
            old_amount,
            old_mode,
            old_tx,
            old_date
        ) = old

        old_money = _money_account(
            old_mode
        )

        reversal_source = (
            f"{payment.pk}:edit-reversal:"
            f"{payment.edited_at.isoformat() if payment.edited_at else 'edit'}"
        )

        if not Voucher.objects.filter(
            source_type="payment_edit_reversal",
            source_id=reversal_source
        ).exists():

            create_voucher(
                voucher_type=Voucher.TYPE_ADJUSTMENT,
                amount=old_amount,
                debit_account=customer_account,
                credit_account=old_money,
                voucher_date=old_date,
                payment_mode=old_mode,
                transaction_id=old_tx,
                party_name=(
                    payment.loan.customer.full_name
                ),
                narration=(
                    f"Verified reversal of "
                    f"edited payment "
                    f"{payment.receipt_number}."
                ),
                source_type="payment_edit_reversal",
                source_id=reversal_source,
            )

    source_id = (
        f"{payment.pk}:current:"
        f"{payment.edited_at.isoformat() if payment.edited_at else 'original'}"
    )

    if Voucher.objects.filter(
        source_type="payment_receipt",
        source_id=source_id
    ).exists():

        return

    (
        principal,
        interest,
        penalty
    ) = _component_split(payment)

    allocated_total = (
        principal
        + interest
        + penalty
    )

    if allocated_total > payment.amount_paid:

        raise ValueError(
            "Accounting allocation exceeds payment amount."
        )

    unallocated = (
        payment.amount_paid
        - allocated_total
    )

    entries = [
        {
            "ledger_account": money,
            "debit": payment.amount_paid,
        }
    ]

    if principal > 0:

        entries.append(
            {
                "ledger_account": customer_account,
                "credit": principal,
            }
        )

    if interest > 0:

        interest_account = (
            get_or_create_named_account(
                "Interest Income",
                LedgerAccount.TYPE_INCOME
            )
        )

        entries.append(
            {
                "ledger_account": interest_account,
                "credit": interest,
            }
        )

    if penalty > 0:

        penalty_account = (
            get_or_create_named_account(
                "Penalty Income",
                LedgerAccount.TYPE_INCOME
            )
        )

        entries.append(
            {
                "ledger_account": penalty_account,
                "credit": penalty,
            }
        )

    if unallocated > 0:

        entries.append(
            {
                "ledger_account": customer_account,
                "credit": unallocated,
            }
        )

    narration = (
        "Loan repayment received via "
        + (
            "Cash"
            if payment.payment_mode
            == Voucher.MODE_CASH
            else "Bank"
        )
        + "."
    )

    create_balanced_voucher(
        voucher_type=Voucher.TYPE_RECEIPT,
        amount=payment.amount_paid,
        entries=entries,
        voucher_date=payment.payment_date,
        payment_mode=payment.payment_mode,
        transaction_id=payment.transaction_id,
        party_name=payment.loan.customer.full_name,
        narration=narration,
        source_type="payment_receipt",
        source_id=source_id,
    )


def _payment_saved(
    sender,
    instance,
    created,
    **kwargs
):

    old = (
        None
        if created
        else getattr(
            instance,
            "_accounting_old",
            None
        )
    )

    if not created:

        if not old:
            return

        current = (
            instance.amount_paid,
            instance.payment_mode,
            instance.transaction_id,
            instance.payment_date,
        )

        if old == current:

            return

    transaction.on_commit(
        lambda: _post_payment_accounting(
            instance.pk,
            old=old
        )
    )


def register():

    from loans.models import Loan
    from payments.models import Payment

    post_save.connect(
        _loan_created,
        sender=Loan,
        weak=False,
        dispatch_uid="accounting_loan_created",
    )

    pre_save.connect(
        _capture_old_payment,
        sender=Payment,
        weak=False,
        dispatch_uid="accounting_capture_payment",
    )

    post_save.connect(
        _payment_saved,
        sender=Payment,
        weak=False,
        dispatch_uid="accounting_payment_saved",
    )