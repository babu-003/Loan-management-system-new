from django.core.management.base import BaseCommand
from django.db import transaction

from accounting.models import Voucher, create_voucher, get_cash_account, get_bank_account, get_customer_account, get_investor_account
from accounting.signals import _post_payment_accounting
from investments.models import InvestmentLedgerEntry
from loans.models import Loan
from payments.models import Payment


class Command(BaseCommand):
    help = "Create missing Accounting vouchers for existing loans, payments and investor deposits."

    def handle(self, *args, **options):
        loan_count = payment_count = deposit_count = 0

        for loan in Loan.objects.select_related("customer").all():
            if Voucher.objects.filter(source_type="loan", source_id=str(loan.pk)).exists():
                continue
            create_voucher(
                voucher_type=Voucher.TYPE_PAYMENT,
                amount=loan.principal_amount,
                debit_account=get_customer_account(loan.customer),
                credit_account=get_cash_account(),
                party_name=loan.customer.full_name,
                voucher_date=loan.start_date,
                narration=f"Loan disbursement for {loan.loan_number}.",
                source_type="loan",
                source_id=str(loan.pk),
            )
            loan_count += 1

        for payment in Payment.objects.all():
            source_id = f"{payment.pk}:current:{payment.edited_at.isoformat() if payment.edited_at else 'original'}"
            if Voucher.objects.filter(source_type="payment_receipt", source_id=source_id).exists():
                continue
            _post_payment_accounting(payment.pk)
            payment_count += 1

        for entry in InvestmentLedgerEntry.objects.select_related("investor").filter(entry_type=InvestmentLedgerEntry.TYPE_DEPOSIT):
            if not entry.investor:
                continue
            source_id = f"investment_deposit:{entry.pk}"
            if Voucher.objects.filter(source_type="investment_deposit", source_id=source_id).exists():
                continue
            # Historical Investment deposits are funding/borrowing, not asset purchases.
            create_voucher(
                voucher_type=Voucher.TYPE_BORROWING,
                amount=entry.amount,
                debit_account=get_cash_account(),
                credit_account=get_investor_account(entry.investor),
                party_name=entry.investor.full_name,
                voucher_date=entry.created_at.date(),
                narration=f"Investor borrowing received from {entry.investor.full_name}.",
                source_type="investment_deposit",
                source_id=source_id,
            )
            deposit_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Accounting sync complete. Loans: {loan_count}, Payments: {payment_count}, Investor deposits: {deposit_count}."
        ))
