from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import PaymentEditForm, PaymentForm, PaymentSearchForm
from .models import Payment, PaymentIDCounter, allocate_payment, reverse_payment_allocations


@login_required
def payment_list(request):
    search_form = PaymentSearchForm(request.GET or None)
    payments = Payment.objects.select_related("loan", "loan__customer")

    if search_form.is_valid():
        query = search_form.cleaned_data.get("q")
        date_from = search_form.cleaned_data.get("date_from")
        date_to = search_form.cleaned_data.get("date_to")
        if query:
            payments = payments.filter(
                Q(receipt_number__icontains=query)
                | Q(loan__loan_number__icontains=query)
                | Q(loan__customer__full_name__icontains=query)
            )
        if date_from:
            payments = payments.filter(payment_date__gte=date_from)
        if date_to:
            payments = payments.filter(payment_date__lte=date_to)

    paginator = Paginator(payments, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "payments/payment_list.html", {"page_obj": page_obj, "search_form": search_form})


@login_required
@transaction.atomic
def payment_create(request):
    initial = {}
    loan_id = request.GET.get("loan")
    if loan_id:
        initial["loan"] = loan_id

    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.receipt_number = PaymentIDCounter.next_receipt_number()
            payment.save()
            allocate_payment(payment)
            if payment.unallocated_amount > 0:
                messages.success(
                    request,
                    f"Payment {payment.receipt_number} recorded. Note: ₹{payment.unallocated_amount} "
                    f"could not be applied — this loan has no remaining balance.",
                )
            else:
                messages.success(request, f"Payment {payment.receipt_number} recorded.")
            return redirect("payments:detail", pk=payment.pk)
    else:
        form = PaymentForm(initial=initial)
    return render(request, "payments/payment_form.html", {"form": form})


@login_required
def payment_detail(request, pk):
    payment = get_object_or_404(
        Payment.objects.select_related("loan", "loan__customer"), pk=pk
    )
    allocations = payment.allocations.select_related("installment").order_by("installment__installment_number")
    return render(
        request, "payments/payment_detail.html", {"payment": payment, "allocations": allocations}
    )


@login_required
@transaction.atomic
def payment_edit(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    if request.method == "POST":
        form = PaymentEditForm(request.POST, instance=payment)
        if form.is_valid():
            new_amount = form.cleaned_data["amount_paid"]
            old_amount = payment.amount_paid
            # Reverse this payment's own allocations first, then reapply
            # the new amount fresh — correct regardless of what other
            # payments have done to the loan's installments since.
            reverse_payment_allocations(payment)
            payment = form.save(commit=False)
            if new_amount != old_amount:
                payment.previous_amount = old_amount
                payment.edited_at = timezone.now()
            payment.save()
            allocate_payment(payment)
            messages.success(request, f"Payment {payment.receipt_number} updated.")
            return redirect("payments:detail", pk=payment.pk)
    else:
        form = PaymentEditForm(instance=payment)
    return render(request, "payments/payment_edit_form.html", {"form": form, "payment": payment})
