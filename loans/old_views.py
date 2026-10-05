from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import InstallmentDueDateForm, LoanForm, LoanGroupForm, LoanSearchForm
from .models import Installment, Loan, LoanGroup


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
    return render(request, "loans/loan_list.html", {"page_obj": page_obj, "search_form": search_form})


@login_required
@transaction.atomic
def loan_create(request):
    initial = {}
    group_id = request.GET.get("group")
    customer_id = request.GET.get("customer")
    if group_id:
        initial["loan_group"] = group_id
    if customer_id:
        initial["customer"] = customer_id

    if request.method == "POST":
        form = LoanForm(request.POST)
        if form.is_valid():
            loan = form.save(commit=False)
            from .models import LoanIDCounter
            loan.loan_number = LoanIDCounter.next_loan_number()
            loan.compute_totals()
            loan.full_clean()
            loan.save()
            loan.generate_installment_schedule()
            messages.success(request, f"Loan {loan.loan_number} created with {loan.number_of_installments} installments.")
            return redirect("loans:detail", pk=loan.pk)
    else:
        form = LoanForm(initial=initial)
    return render(request, "loans/loan_form.html", {"form": form})


@login_required
def loan_detail(request, pk):
    loan = get_object_or_404(Loan.objects.select_related("customer", "loan_group", "loan_type", "interest_type"), pk=pk)
    installments = loan.installments.all()
    return render(request, "loans/loan_detail.html", {"loan": loan, "installments": installments})


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
            messages.success(request, f"Group {group.group_id} created. Add member loans to it now.")
            return redirect("loans:group_detail", pk=group.pk)
    else:
        form = LoanGroupForm()
    return render(request, "loans/loangroup_form.html", {"form": form})


@login_required
def loan_group_detail(request, pk):
    group = get_object_or_404(LoanGroup, pk=pk)
    return render(request, "loans/loangroup_detail.html", {"group": group, "loans": group.loans.select_related("customer")})
