from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class LedgerAccount(models.Model):

    TYPE_CASH = "cash"
    TYPE_BANK = "bank"
    TYPE_CUSTOMER = "customer"
    TYPE_EXPENSE = "expense"
    TYPE_BORROWING = "borrowing"
    TYPE_INVESTMENT = "investment"
    TYPE_INCOME = "income"
    TYPE_OTHER = "other"

    TYPE_CHOICES = [
        (TYPE_CASH, "Cash"),
        (TYPE_BANK, "Bank"),
        (TYPE_CUSTOMER, "Customer"),
        (TYPE_EXPENSE, "Expense"),
        (TYPE_BORROWING, "Borrowing"),
        (TYPE_INVESTMENT, "Investment"),
        (TYPE_INCOME, "Income"),
        (TYPE_OTHER, "Other"),
    ]

    name = models.CharField(max_length=150)

    account_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES
    )

    customer = models.ForeignKey(
        "customers.Customer",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="accounting_ledgers",
    )

    investor = models.ForeignKey(
        "investments.Investor",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="accounting_ledgers",
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["account_type", "name"]

        constraints = [
            models.UniqueConstraint(
                fields=["account_type", "name"],
                name="unique_ledger_account_name_type"
            )
        ]

    def __str__(self):
        return self.name

    @property
    def balance(self):

        debit = (
            self.entries.aggregate(v=models.Sum("debit"))["v"]
            or Decimal("0")
        )

        credit = (
            self.entries.aggregate(v=models.Sum("credit"))["v"]
            or Decimal("0")
        )

        if self.account_type in {
            self.TYPE_CASH,
            self.TYPE_BANK,
            self.TYPE_CUSTOMER,
            self.TYPE_EXPENSE,
            self.TYPE_INVESTMENT,
        }:
            return debit - credit

        return credit - debit


class VoucherCategory(models.Model):

    TYPE_EXPENSE = "expense"
    TYPE_BORROWING = "borrowing"
    TYPE_REPAYMENT = "repayment"
    TYPE_INVESTMENT = "investment"
    TYPE_INCOME = "income"
    TYPE_OTHER = "other"

    TYPE_CHOICES = [
        (TYPE_EXPENSE, "Expense"),
        (TYPE_BORROWING, "Borrowing"),
        (TYPE_REPAYMENT, "Repayment"),
        (TYPE_INVESTMENT, "Investment"),
        (TYPE_INCOME, "Income"),
        (TYPE_OTHER, "Other"),
    ]

    name = models.CharField(
        max_length=100,
        unique=True
    )

    voucher_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES
    )

    ledger_account = models.ForeignKey(
        LedgerAccount,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="categories",
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["voucher_type", "name"]

    def __str__(self):
        return self.name


class Voucher(models.Model):

    TYPE_RECEIPT = "receipt"
    TYPE_PAYMENT = "payment"
    TYPE_EXPENSE = "expense"
    TYPE_BORROWING = "borrowing"
    TYPE_REPAYMENT = "repayment"
    TYPE_INVESTMENT = "investment"
    TYPE_INCOME = "income"
    TYPE_JOURNAL = "journal"
    TYPE_ADJUSTMENT = "adjustment"

    TYPE_CHOICES = [
        (TYPE_RECEIPT, "Receipt"),
        (TYPE_PAYMENT, "Payment"),
        (TYPE_EXPENSE, "Expense"),
        (TYPE_BORROWING, "Borrowing"),
        (TYPE_REPAYMENT, "Repayment"),
        (TYPE_INVESTMENT, "Investment"),
        (TYPE_INCOME, "Income"),
        (TYPE_JOURNAL, "Journal"),
        (TYPE_ADJUSTMENT, "Adjustment"),
    ]

    STANDARD_TYPES = (
        TYPE_EXPENSE,
        TYPE_INVESTMENT,
        TYPE_INCOME,
    )

    MODE_CASH = "cash"
    MODE_ONLINE = "online"
    MODE_UPI = "upi"
    MODE_CHEQUE = "cheque"

    MODE_CHOICES = [
        (MODE_CASH, "Cash"),
        (MODE_ONLINE, "Online / Bank"),
        (MODE_UPI, "UPI"),
        (MODE_CHEQUE, "Cheque"),
    ]

    voucher_number = models.CharField(
        max_length=30,
        unique=True,
        editable=False
    )

    voucher_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES
    )

    voucher_date = models.DateField(
        default=timezone.localdate
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2
    )

    payment_mode = models.CharField(
        max_length=10,
        choices=MODE_CHOICES,
        default=MODE_CASH
    )

    transaction_id = models.CharField(
        max_length=100,
        blank=True
    )

    category = models.ForeignKey(
        VoucherCategory,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="vouchers"
    )

    party_name = models.CharField(
        max_length=150,
        blank=True
    )

    narration = models.TextField(
        blank=True
    )

    source_type = models.CharField(
        max_length=50,
        blank=True
    )

    source_id = models.CharField(
        max_length=100,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-voucher_date", "-created_at"]

    def __str__(self):
        return (
            f"{self.voucher_number} — "
            f"{self.get_voucher_type_display()} — "
            f"₹{self.amount}"
        )

    @classmethod
    def next_number(cls):

        from core.models import get_setting

        prefix = get_setting(
            "voucher_id_prefix",
            "VCH"
        )

        padding = int(
            get_setting(
                "id_number_padding",
                "6"
            )
        )

        with transaction.atomic():

            counter, _ = VoucherCounter.objects.select_for_update().get_or_create(
                pk=1
            )

            counter.last_number += 1

            counter.save(
                update_fields=["last_number"]
            )

            return f"{prefix}-{counter.last_number:0{padding}d}"

    def save(self, *args, **kwargs):

        if not self.voucher_number:
            self.voucher_number = self.next_number()

        super().save(*args, **kwargs)


class VoucherCounter(models.Model):

    last_number = models.PositiveIntegerField(
        default=0
    )


class VoucherEntry(models.Model):

    voucher = models.ForeignKey(
        Voucher,
        on_delete=models.CASCADE,
        related_name="entries"
    )

    ledger_account = models.ForeignKey(
        LedgerAccount,
        on_delete=models.PROTECT,
        related_name="entries"
    )

    debit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0")
    )

    credit = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0")
    )

    narration = models.CharField(
        max_length=255,
        blank=True
    )

    def clean(self):

        if (self.debit > 0) == (self.credit > 0):
            raise ValidationError(
                "A ledger entry must contain either Debit or Credit, not both."
            )

        if (
            self.credit > 0
            and self.ledger_account.account_type
            == LedgerAccount.TYPE_EXPENSE
        ):

            if (
                self.voucher.voucher_type
                != Voucher.TYPE_ADJUSTMENT
                or self.voucher.source_type
                not in {
                    "verified_vendor_refund",
                    "verified_rectification",
                }
            ):

                raise ValidationError(
                    "An Expense ledger can only be credited "
                    "by a verified vendor refund or rectification."
                )

    def __str__(self):

        side = (
            f"Dr ₹{self.debit}"
            if self.debit
            else f"Cr ₹{self.credit}"
        )

        return f"{self.ledger_account.name} — {side}"


def get_cash_account():

    return LedgerAccount.objects.get_or_create(
        account_type=LedgerAccount.TYPE_CASH,
        name="Cash"
    )[0]


def get_bank_account():

    return LedgerAccount.objects.get_or_create(
        account_type=LedgerAccount.TYPE_BANK,
        name="Bank"
    )[0]


def get_customer_account(customer):

    account, _ = LedgerAccount.objects.get_or_create(
        account_type=LedgerAccount.TYPE_CUSTOMER,
        name=(
            f"Customer - "
            f"{customer.customer_id} - "
            f"{customer.full_name}"
        ),
        defaults={
            "customer": customer
        },
    )

    if account.customer_id != customer.pk:

        account.customer = customer

        account.save(
            update_fields=["customer"]
        )

    return account


def get_investor_account(investor):

    account, _ = LedgerAccount.objects.get_or_create(
        account_type=LedgerAccount.TYPE_BORROWING,
        name=(
            f"Investor - "
            f"{investor.investor_id} - "
            f"{investor.full_name}"
        ),
        defaults={
            "investor": investor
        },
    )

    if account.investor_id != investor.pk:

        account.investor = investor

        account.save(
            update_fields=["investor"]
        )

    return account


def get_or_create_named_account(
    name,
    account_type
):

    return LedgerAccount.objects.get_or_create(
        name=name,
        account_type=account_type
    )[0]


def ensure_category_account(category):

    if category is None:
        raise ValueError(
            "A voucher category is required."
        )

    mapping = {
        VoucherCategory.TYPE_EXPENSE:
            LedgerAccount.TYPE_EXPENSE,

        VoucherCategory.TYPE_INVESTMENT:
            LedgerAccount.TYPE_INVESTMENT,

        VoucherCategory.TYPE_INCOME:
            LedgerAccount.TYPE_INCOME,
    }

    account_type = mapping.get(
        category.voucher_type
    )

    if not account_type:

        raise ValueError(
            "This category cannot be used for "
            "a standard Expense, Investment or Income voucher."
        )

    account = category.ledger_account

    if (
        account is None
        or account.account_type != account_type
        or not account.is_active
    ):

        account = get_or_create_named_account(
            category.name,
            account_type
        )

        category.ledger_account = account

        category.save(
            update_fields=["ledger_account"]
        )

    return account


def _validate_standard_accounts(
    voucher_type,
    debit_account,
    credit_account
):

    if (
        voucher_type == Voucher.TYPE_EXPENSE
        and credit_account.account_type
        not in {
            LedgerAccount.TYPE_CASH,
            LedgerAccount.TYPE_BANK,
        }
    ):

        raise ValueError(
            "Expense credit account must be Cash or Bank."
        )

    if (
        voucher_type == Voucher.TYPE_INVESTMENT
        and debit_account.account_type
        != LedgerAccount.TYPE_INVESTMENT
    ):

        raise ValueError(
            "Investment debit account must be an Investment asset ledger."
        )

    if (
        voucher_type == Voucher.TYPE_INCOME
        and credit_account.account_type
        != LedgerAccount.TYPE_INCOME
    ):

        raise ValueError(
            "Income credit account must be an Income ledger."
        )

    if (
        credit_account.account_type
        == LedgerAccount.TYPE_EXPENSE
        and voucher_type != Voucher.TYPE_ADJUSTMENT
    ):

        raise ValueError(
            "Expense ledgers cannot be credited by normal vouchers."
        )


def create_balanced_voucher(
    *,
    voucher_type,
    amount,
    entries,
    voucher_date=None,
    payment_mode="cash",
    transaction_id="",
    category=None,
    party_name="",
    narration="",
    source_type="",
    source_id=""
):

    if amount <= 0:
        raise ValueError(
            "Voucher amount must be greater than zero."
        )

    if payment_mode == Voucher.MODE_CASH:
        transaction_id = ""

    debit_total = sum(
        (
            Decimal(str(entry.get("debit", 0)))
            for entry in entries
        ),
        Decimal("0")
    )

    credit_total = sum(
        (
            Decimal(str(entry.get("credit", 0)))
            for entry in entries
        ),
        Decimal("0")
    )

    if debit_total != credit_total:
        raise ValueError(
            f"Voucher is not balanced. "
            f"Debit = {debit_total}, "
            f"Credit = {credit_total}."
        )

    if debit_total != amount:
        raise ValueError(
            f"Voucher amount mismatch. "
            f"Amount = {amount}, "
            f"entries = {debit_total}."
        )

    with transaction.atomic():

        voucher = Voucher.objects.create(
            voucher_type=voucher_type,
            voucher_date=voucher_date or timezone.localdate(),
            amount=amount,
            payment_mode=payment_mode,
            transaction_id=transaction_id,
            category=category,
            party_name=party_name,
            narration=narration,
            source_type=source_type,
            source_id=source_id,
        )

        for entry in entries:

            debit = Decimal(
                str(entry.get("debit", 0))
            )

            credit = Decimal(
                str(entry.get("credit", 0))
            )

            voucher_entry = VoucherEntry(
                voucher=voucher,
                ledger_account=entry["ledger_account"],
                debit=debit,
                credit=credit,
                narration=entry.get(
                    "narration",
                    ""
                ),
            )

            voucher_entry.full_clean()

            voucher_entry.save()

        return voucher


def create_voucher(
    *,
    voucher_type,
    amount,
    debit_account,
    credit_account,
    voucher_date=None,
    payment_mode="cash",
    transaction_id="",
    category=None,
    party_name="",
    narration="",
    source_type="",
    source_id=""
):

    _validate_standard_accounts(
        voucher_type,
        debit_account,
        credit_account
    )

    return create_balanced_voucher(
        voucher_type=voucher_type,
        amount=amount,
        entries=[
            {
                "ledger_account": debit_account,
                "debit": amount,
            },
            {
                "ledger_account": credit_account,
                "credit": amount,
            },
        ],
        voucher_date=voucher_date,
        payment_mode=payment_mode,
        transaction_id=transaction_id,
        category=category,
        party_name=party_name,
        narration=narration,
        source_type=source_type,
        source_id=source_id,
    )