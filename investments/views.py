from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import DepositEditForm, DepositForm, InvestorForm, LedgerFilterForm
from .models import (
    InvestmentLedgerEntry,
    InvestmentPoolBalance,
    Investor,
    edit_deposit,
    record_ledger_entry,
)


@login_required
def investor_list(request):
    investors = Investor.objects.all()
    return render(
        request, "investments/investor_list.html",
        {"investors": investors, "pool_balance": InvestmentPoolBalance.get_balance()},
    )


@login_required
def investor_add(request):
    if request.method == "POST":
        form = InvestorForm(request.POST)
        if form.is_valid():
            investor = form.save()
            messages.success(request, f"Investor {investor.investor_id} added.")
            return redirect("investments:investor_detail", pk=investor.pk)
    else:
        form = InvestorForm()
    return render(request, "investments/investor_form.html", {"form": form})


@login_required
def investor_detail(request, pk):
    investor = get_object_or_404(Investor, pk=pk)
    entries = investor.ledger_entries.all()
    return render(
        request, "investments/investor_detail.html", {"investor": investor, "entries": entries}
    )


@login_required
def deposit_add(request):
    initial = {}
    investor_pk = request.GET.get("investor")

    if investor_pk:
        initial["investor"] = investor_pk

    if request.method == "POST":
        form = DepositForm(request.POST)

        if form.is_valid():
            investor = form.cleaned_data["investor"]
            amount = form.cleaned_data["amount"]

            # Create the investment ledger entry and store it.
            entry = record_ledger_entry(
                InvestmentLedgerEntry.TYPE_DEPOSIT,
                amount=amount,
                investor=investor,
                notes=form.cleaned_data.get("notes", ""),
            )

            from accounting.models import (
                Voucher,
                create_voucher,
                get_investor_account,
                get_cash_account,
                get_bank_account,
            )

            money_account = (
                get_cash_account()
                if form.cleaned_data["payment_mode"] == "cash"
                else get_bank_account()
            )

            create_voucher(
                voucher_type=Voucher.TYPE_BORROWING,
                amount=amount,
                debit_account=money_account,
                credit_account=get_investor_account(investor),
                voucher_date=timezone.localdate(),
                payment_mode=form.cleaned_data["payment_mode"],
                transaction_id=form.cleaned_data.get("transaction_id", ""),
                party_name=investor.full_name,
                narration=(
                    form.cleaned_data.get("notes", "")
                    or f"Investor borrowing received from {investor.full_name}."
                ),
                source_type="investment_deposit",
                source_id=f"investment_deposit:{entry.pk}",
            )

            messages.success(
                request,
                f"Deposit of Rs. {amount} recorded for {investor.full_name}.",
            )

            return redirect(
                "investments:investor_detail",
                pk=investor.pk,
            )

    else:
        form = DepositForm(initial=initial)

    return render(
        request,
        "investments/deposit_form.html",
        {"form": form},
    )


@login_required
def ledger_list(request):
    form = LedgerFilterForm(request.GET or None)
    entries = InvestmentLedgerEntry.objects.select_related("investor", "loan", "payment")

    if form.is_valid():
        entry_type = form.cleaned_data.get("entry_type")
        investor = form.cleaned_data.get("investor")
        date_from = form.cleaned_data.get("date_from")
        date_to = form.cleaned_data.get("date_to")
        if entry_type:
            entries = entries.filter(entry_type=entry_type)
        if investor:
            entries = entries.filter(investor=investor)
        if date_from:
            entries = entries.filter(created_at__date__gte=date_from)
        if date_to:
            entries = entries.filter(created_at__date__lte=date_to)

    paginator = Paginator(entries, 30)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request, "investments/ledger_list.html",
        {"page_obj": page_obj, "form": form, "pool_balance": InvestmentPoolBalance.get_balance()},
    )


@login_required
def deposit_edit(request, pk):
    entry = get_object_or_404(InvestmentLedgerEntry, pk=pk, entry_type=InvestmentLedgerEntry.TYPE_DEPOSIT)
    if request.method == "POST":
        form = DepositEditForm(request.POST)
        if form.is_valid():
            new_amount = form.cleaned_data["amount"]
            entry, adjustment = edit_deposit(entry, new_amount)
            if adjustment:
                messages.success(
                    request,
                    f"Deposit updated to Rs. {new_amount}. "
                    f"An adjustment of Rs. {adjustment.amount} was recorded in the Invest Log.",
                )
            else:
                messages.info(request, "Amount unchanged.")
            return redirect("investments:investor_detail", pk=entry.investor.pk)
    else:
        form = DepositEditForm(initial={"amount": entry.amount})
    return render(request, "investments/deposit_edit_form.html", {"form": form, "entry": entry})
