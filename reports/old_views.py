import csv

from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from customers.models import Customer
from loans.models import Installment, Loan
from payments.models import Payment
from investments.models import InvestmentPoolBalance

from .forms import DateRangeForm


def _decimal_sum(queryset, expression, field_name="total"):
    result = queryset.aggregate(**{field_name: Sum(expression)})[field_name]
    return result or 0


@login_required
def dashboard(request):
    today = timezone.localdate()

    active_loans = Loan.objects.filter(status=Loan.STATUS_ACTIVE)
    total_payable_active = _decimal_sum(active_loans, "total_payable")
    total_paid_active = _decimal_sum(
        Installment.objects.filter(loan__status=Loan.STATUS_ACTIVE), "paid_amount"
    )
    total_outstanding = total_payable_active - total_paid_active

    overdue_qs = Installment.objects.filter(due_date__lt=today).exclude(status=Installment.STATUS_PAID)
    overdue_amount = _decimal_sum(overdue_qs, F("due_amount") - F("paid_amount"))

    upcoming_qs = Installment.objects.filter(
        due_date__gte=today, due_date__lte=today + timezone.timedelta(days=7)
    ).exclude(status=Installment.STATUS_PAID)
    upcoming_amount = _decimal_sum(upcoming_qs, F("due_amount") - F("paid_amount"))

    context = {
        "total_customers": Customer.objects.filter(status=Customer.STATUS_ACTIVE).count(),
        "total_loans_active": active_loans.count(),
        "total_loans_completed": Loan.objects.filter(status=Loan.STATUS_COMPLETED).count(),
        "total_principal_disbursed": _decimal_sum(
            Loan.objects.filter(status__in=[Loan.STATUS_ACTIVE, Loan.STATUS_COMPLETED]), "principal_amount"
        ),
        "total_outstanding": total_outstanding,
        "total_collected_all_time": _decimal_sum(Payment.objects.all(), "amount_paid"),
        "total_collected_this_month": _decimal_sum(
            Payment.objects.filter(payment_date__year=today.year, payment_date__month=today.month),
            "amount_paid",
        ),
        "total_invested": InvestmentPoolBalance.get_balance(),
        "overdue_count": overdue_qs.count(),
        "overdue_amount": overdue_amount,
        "upcoming_count": upcoming_qs.count(),
        "upcoming_amount": upcoming_amount,
    }
    return render(request, "reports/dashboard.html", context)


@login_required
def overdue_report(request):
    today = timezone.localdate()
    installments = (
        Installment.objects.filter(due_date__lt=today)
        .exclude(status=Installment.STATUS_PAID)
        .select_related("loan", "loan__customer")
        .order_by("due_date")
    )
    rows = [
        {
            "installment": installment,
            "days_overdue": (today - installment.due_date).days,
        }
        for installment in installments
    ]
    rows.sort(key=lambda row: row["days_overdue"], reverse=True)
    total_overdue = sum(row["installment"].balance_amount for row in rows)
    return render(
        request, "reports/overdue_report.html", {"rows": rows, "total_overdue": total_overdue}
    )


def _collection_queryset(request):
    form = DateRangeForm(request.GET or None)
    payments = Payment.objects.select_related("loan", "loan__customer").order_by("payment_date")
    if form.is_valid():
        if form.cleaned_data.get("date_from"):
            payments = payments.filter(payment_date__gte=form.cleaned_data["date_from"])
        if form.cleaned_data.get("date_to"):
            payments = payments.filter(payment_date__lte=form.cleaned_data["date_to"])
    return form, payments


@login_required
def collection_report(request):
    form, payments = _collection_queryset(request)
    total = _decimal_sum(payments, "amount_paid")
    return render(
        request,
        "reports/collection_report.html",
        {"form": form, "payments": payments, "total": total},
    )


@login_required
def collection_report_csv(request):
    _, payments = _collection_queryset(request)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="collection_report.csv"'
    writer = csv.writer(response)
    writer.writerow(["Receipt No.", "Date", "Loan No.", "Customer", "Amount"])
    for payment in payments:
        writer.writerow([
            payment.receipt_number, payment.payment_date, payment.loan.loan_number,
            payment.loan.customer.full_name, payment.amount_paid,
        ])
    return response
