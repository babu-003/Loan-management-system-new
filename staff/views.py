from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from loans.models import Loan

from .forms import StaffAssignmentForm, StaffForm
from .models import Staff


@login_required
def staff_list(request):
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")

    staff_qs = Staff.objects.annotate(
        assigned_count=Count("loans", distinct=True),
        active_count=Count("loans", filter=Q(loans__status=Loan.STATUS_ACTIVE), distinct=True),
        completed_count=Count("loans", filter=Q(loans__status=Loan.STATUS_COMPLETED), distinct=True),
    )
    if query:
        staff_qs = staff_qs.filter(
            Q(full_name__icontains=query) | Q(employee_id__icontains=query) | Q(mobile__icontains=query)
        )
    if status:
        staff_qs = staff_qs.filter(status=status)

    context = {
        "staff_list": staff_qs,
        "query": query,
        "selected_status": status,
        "status_choices": Staff.STATUS_CHOICES,
        "active_count": Staff.objects.filter(status=Staff.STATUS_ACTIVE).count(),
        "total_count": Staff.objects.count(),
    }
    return render(request, "staff/staff_list.html", context)


@login_required
def staff_create(request):
    if request.method == "POST":
        form = StaffForm(request.POST)
        if form.is_valid():
            staff = form.save()
            messages.success(request, f"Staff {staff.full_name} created successfully.")
            return redirect("staff:detail", pk=staff.pk)
    else:
        form = StaffForm()
    return render(request, "staff/staff_form.html", {"form": form, "title": "Create Staff"})


@login_required
def staff_detail(request, pk):
    staff = get_object_or_404(Staff, pk=pk)
    loans = staff.loans.select_related("customer", "loan_type").prefetch_related("payments", "installments")
    status_filter = request.GET.get("status", "")
    if status_filter in dict(Loan.STATUS_CHOICES):
        loans = loans.filter(status=status_filter)

    context = {
        "staff": staff,
        "loans": loans,
        "status_filter": status_filter,
        "loan_status_choices": Loan.STATUS_CHOICES,
    }
    return render(request, "staff/staff_detail.html", context)


@login_required
def staff_edit(request, pk):
    staff = get_object_or_404(Staff, pk=pk)
    if request.method == "POST":
        form = StaffForm(request.POST, instance=staff)
        if form.is_valid():
            form.save()
            messages.success(request, f"Staff {staff.full_name} updated.")
            return redirect("staff:detail", pk=staff.pk)
    else:
        form = StaffForm(instance=staff)
    return render(request, "staff/staff_form.html", {"form": form, "title": "Edit Staff", "staff": staff})


@login_required
def assign_loan(request, pk):
    loan = get_object_or_404(Loan.objects.select_related("customer"), pk=pk)
    if request.method != "POST":
        return redirect("loans:detail", pk=loan.pk)

    form = StaffAssignmentForm(request.POST)
    if form.is_valid():
        staff = form.cleaned_data["staff"]
        loan.assigned_staff = staff
        loan.save(update_fields=["assigned_staff"])
        if staff:
            messages.success(request, f"{loan.loan_number} assigned to {staff.full_name}.")
        else:
            messages.success(request, f"{loan.loan_number} is now unassigned.")
    else:
        messages.error(request, "Please select a valid active staff member.")
    return redirect("loans:detail", pk=loan.pk)
