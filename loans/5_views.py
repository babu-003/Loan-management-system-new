from decimal import Decimal
import math

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import InstallmentDueDateForm, LoanForm, LoanGroupForm, LoanGroupMemberForm, LoanSearchForm
from .models import Installment, Loan, LoanGroup, LoanGroupMember

DONUT_RADIUS = 60
DONUT_CIRCUMFERENCE = 2 * math.pi * DONUT_RADIUS

STATUS_COLORS = {
    Loan.STATUS_ACTIVE: "var(--color-primary)",
    Loan.STATUS_COMPLETED: "var(--color-success)",
    Loan.STATUS_CLOSED: "var(--color-muted)",
    Loan.STATUS_CANCELLED: "var(--color-danger)",
}


def _portfolio_donut_segments():
    """Precomputes SVG stroke-dasharray/offset for each status segment —
    done here in Python (not the template) since Django templates can't
    do the trigonometry, and it keeps the template a pure render step."""
    counts = {
        status: Loan.objects.filter(status=status).count()
        for status, _ in Loan.STATUS_CHOICES
    }
    total = sum(counts.values())
    segments = []
    cumulative = 0
    for status, label in Loan.STATUS_CHOICES:
        count = counts[status]
        if not count:
            continue
        dash = (count / total) * DONUT_CIRCUMFERENCE if total else 0
        segments.append({
            "label": label, "count": count, "color": STATUS_COLORS[status],
            "percent": round((count / total) * 100) if total else 0,
            "dasharray": f"{dash:.2f} {DONUT_CIRCUMFERENCE - dash:.2f}",
            "dashoffset": f"{-cumulative:.2f}",
        })
        cumulative += dash
    return segments, total


@login_required
def loan_list(request):
    search_form = LoanSearchForm(request.GET or None)
    loans = Loan.objects.select_related("customer", "loan_type", "loan_group")

    if search_form.is_valid():
        query = search_form.cleaned_data.get("q")
        status = search_form.cleaned_data.get("status")
        loan_type = search_form.cleaned_data.get("loan_type")
        if query:
            loans = loans.filter(
                Q(loan_number__icontains=query)
                | Q(customer__full_name__icontains=query)
                | Q(customer__customer_id__icontains=query)
            )
        if status:
            loans = loans.filter(status=status)
        if loan_type:
            loans = loans.filter(loan_type=loan_type)

    paginator = Paginator(loans, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    donut_segments, total_loans = _portfolio_donut_segments()
    active_loans = Loan.objects.filter(status=Loan.STATUS_ACTIVE)
    total_outstanding = sum((loan.total_outstanding for loan in active_loans), start=Decimal("0"))

    return render(request, "loans/loan_list.html", {
        "page_obj": page_obj, "search_form": search_form,
        "total_loans": total_loans, "total_outstanding": total_outstanding,
        "active_count": active_loans.count(),
        "completed_count": Loan.objects.filter(status=Loan.STATUS_COMPLETED).count(),
        "donut_segments": donut_segments, "donut_radius": DONUT_RADIUS,
    })


@login_required
@transaction.atomic
def loan_create(request,group_pk=None):
    initial = {}
    group_id = request.GET.get("group") or request.POST.get("loan_group")
    customer_id = request.GET.get("customer")
    group = None
    if group_pk:
        group = get_object_or_404(LoanGroup, pk=group_pk)
    if group_id:
        group = get_object_or_404(LoanGroup, pk=group_id, status=LoanGroup.STATUS_ACTIVE)
        initial["loan_group"] = group.pk
    if customer_id:
        initial["customer"] = customer_id

    if request.method == "POST":
        form = LoanForm(request.POST, group=group)
        if form.is_valid():
            loan = form.save(commit=False)
            if group is not None:
                loan.loan_group = group
            from .models import LoanIDCounter
            loan.loan_number = LoanIDCounter.next_loan_number()
            loan.compute_totals()
            loan.full_clean()
            loan.save()
            loan.generate_installment_schedule()
            messages.success(request, f"Loan {loan.loan_number} created with {loan.number_of_installments} installments.")
            return redirect("loans:detail", pk=loan.pk)
    else:
        form = LoanForm(initial=initial, group=group)
    return render(request, "loans/loan_form.html", {"form": form, "group": group})


@login_required
def loan_detail(request, pk):
    loan = get_object_or_404(Loan.objects.select_related("customer", "loan_group", "loan_type", "interest_type"), pk=pk)
    installments = loan.installments.all()
    progress_percent = 0
    if loan.total_payable:
        progress_percent = min(100, round((loan.total_paid / loan.total_payable) * 100))
    return render(request, "loans/loan_detail.html", {
        "loan": loan, "installments": installments, "progress_percent": progress_percent,
    })


@login_required
def installment_edit_due_date(request, pk, installment_id):
    installment = get_object_or_404(Installment, pk=installment_id, loan_id=pk)
    if request.method == "POST":
        form = InstallmentDueDateForm(request.POST, instance=installment)
        if form.is_valid():
            form.save()
            messages.success(request, f"Installment {installment.installment_number} due date updated.")
            return redirect("loans:detail", pk=pk)
    else:
        form = InstallmentDueDateForm(instance=installment)
    return render(
        request, "loans/installment_edit_form.html", {"form": form, "installment": installment}
    )


@login_required
def loan_group_list(request):
    groups = LoanGroup.objects.all()
    return render(request, "loans/loangroup_list.html", {"groups": groups})


@login_required
def loan_group_create(request):
    if request.method == "POST":
        form = LoanGroupForm(request.POST)
        if form.is_valid():
            group = form.save()
            messages.success(request, f"Group {group.group_id} created. Add members to it now.")
            return redirect("loans:group_detail", pk=group.pk)
    else:
        form = LoanGroupForm()
    return render(request, "loans/loangroup_form.html", {"form": form})


@login_required
@transaction.atomic
def loan_group_add_member(request, pk):
    group = get_object_or_404(LoanGroup, pk=pk, status=LoanGroup.STATUS_ACTIVE)
    if request.method == "POST":
        form = LoanGroupMemberForm(request.POST, group=group)
        if form.is_valid():
            customer = form.cleaned_data["customer"]
            # Customer cannot belong to another group
            
            if LoanGroupMember.objects.filter(customer=customer).exists():
                messages.error(request,"This customer is already a member of another group.")
                return redirect("loans:group_add_member", pk=group.pk)
            
             # Add customer to this group
            LoanGroupMember.objects.create(group=group,customer=customer,)
              # If customer already has a loan, attach it to this group
            existing_loan = (Loan.objects.filter(customer=customer).exclude(loan_group=group).order_by("-id").first())
            
            if existing_loan:
                existing_loan.loan_group = group
                existing_loan.save(update_fields=["loan_group"])
            return redirect("loans:group_add_loan", group_pk=group.pk)
    else:
        form = LoanGroupMemberForm(group=group)
    return render(
        request,
        "loans/loangroup_add_member.html",
        {"group": group, "form": form},
    )


@login_required
def loan_group_detail(request, pk):
    group = get_object_or_404(LoanGroup, pk=pk)
    members = group.members.select_related("customer").prefetch_related("customer__loans")
    return render(
        request,
        "loans/loangroup_detail.html",
        {
            "group": group,
            "members": members,
            "loans": group.loans.select_related("customer"),
        },
    )


from .forms import LoanCalculatorForm  # noqa: E402


@login_required
def loan_calculator(request):
    result = None
    if request.method == "POST":
        form = LoanCalculatorForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            temp_loan = Loan(
                principal_amount=data["principal_amount"],
                interest_rate=data["interest_rate"],
                repayment_frequency=data["repayment_frequency"],
                custom_interval_days=data.get("custom_interval_days"),
                number_of_installments=data["number_of_installments"],
                first_due_date=data.get("first_due_date"),
            )
            show_dates = bool(data.get("first_due_date"))

            flat_interest = temp_loan.calculate_flat_interest()
            temp_loan.total_interest = flat_interest
            temp_loan.total_payable = temp_loan.principal_amount + flat_interest
            flat_rows = temp_loan._flat_schedule_rows()
            flat_schedule = [
                {
                    "number": i + 1,
                    "due_date": temp_loan._due_date_for_index(i) if show_dates else None,
                    "principal": p, "interest": interest, "amount": a,
                }
                for i, (p, interest, a) in enumerate(flat_rows)
            ]

            reducing_rows, reducing_interest = temp_loan._reducing_balance_schedule()
            reducing_schedule = [
                {
                    "number": i + 1,
                    "due_date": temp_loan._due_date_for_index(i) if show_dates else None,
                    "principal": p, "interest": interest, "amount": a,
                }
                for i, (p, interest, a) in enumerate(reducing_rows)
            ]

            max_interest = max(flat_interest, reducing_interest) or Decimal("1")
            result = {
                "principal": temp_loan.principal_amount,
                "flat_total_interest": flat_interest,
                "flat_total_payable": temp_loan.principal_amount + flat_interest,
                "flat_schedule": flat_schedule,
                "flat_bar_pct": round((flat_interest / max_interest) * 100),
                "reducing_total_interest": reducing_interest,
                "reducing_total_payable": temp_loan.principal_amount + reducing_interest,
                "reducing_schedule": reducing_schedule,
                "reducing_bar_pct": round((reducing_interest / max_interest) * 100),
            }
    else:
        form = LoanCalculatorForm()
    return render(request, "loans/loan_calculator.html", {"form": form, "result": result})
