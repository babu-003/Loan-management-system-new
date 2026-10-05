from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.storage import FileSystemStorage
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import DetailView, UpdateView
from formtools.wizard.views import SessionWizardView

from django.conf import settings

from documents.models import CustomerDocument

from .forms import (
    AddressForm,
    BankDetailForm,
    CustomerSearchForm,
    DocumentFormSet,
    PersonalDetailsForm,
    ReferenceFormSet,
)
from .models import Customer, CustomerBankDetail, CustomerReference

WIZARD_STEP_PERSONAL = "personal"
WIZARD_STEP_ADDRESS = "address"
WIZARD_STEP_REFERENCE = "reference"
WIZARD_STEP_BANK = "bank"
WIZARD_STEP_DOCUMENTS = "documents"

WIZARD_STEP_LABELS = {
    WIZARD_STEP_PERSONAL: "Personal Details",
    WIZARD_STEP_ADDRESS: "Address",
    WIZARD_STEP_REFERENCE: "Reference / Family",
    WIZARD_STEP_BANK: "Bank Details",
    WIZARD_STEP_DOCUMENTS: "KYC Documents",
}

wizard_file_storage = FileSystemStorage(
    location=str(settings.MEDIA_ROOT / "wizard_tmp")
)


class CustomerWizard(LoginRequiredMixin, SessionWizardView):
    """Multi-step "Add Customer" flow (§60 of the spec: no single giant
    form). Every section is compulsory — Personal, Address, at least one
    Reference, Bank Details, and at least one KYC document — nothing is
    persisted to the database until the final step, inside one atomic
    transaction."""

    file_storage = wizard_file_storage
    form_list = [
        (WIZARD_STEP_PERSONAL, PersonalDetailsForm),
        (WIZARD_STEP_ADDRESS, AddressForm),
        (WIZARD_STEP_REFERENCE, ReferenceFormSet),
        (WIZARD_STEP_BANK, BankDetailForm),
        (WIZARD_STEP_DOCUMENTS, DocumentFormSet),
    ]
    template_name = "customers/customer_wizard_form.html"

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form=form, **kwargs)
        current_step = self.steps.current
        all_steps = list(self.get_form_list().keys())
        current_index = all_steps.index(current_step)
        context["step_pills"] = [
            {
                "label": WIZARD_STEP_LABELS[step_name],
                "state": (
                    "current" if step_name == current_step
                    else "done" if index < current_index
                    else ""
                ),
            }
            for index, step_name in enumerate(all_steps)
        ]
        context["current_step_label"] = WIZARD_STEP_LABELS[current_step]
        return context

    @transaction.atomic
    def done(self, form_list, form_dict, **kwargs):
        personal_form = form_dict[WIZARD_STEP_PERSONAL]
        address_form = form_dict[WIZARD_STEP_ADDRESS]
        reference_formset = form_dict[WIZARD_STEP_REFERENCE]
        bank_form = form_dict[WIZARD_STEP_BANK]
        document_formset = form_dict[WIZARD_STEP_DOCUMENTS]

        customer = personal_form.save(commit=False)
        for field_name, value in address_form.cleaned_data.items():
            setattr(customer, field_name, value)
        customer.full_clean(exclude=["customer_id"])
        customer.save()

        for reference_data in reference_formset.cleaned_data:
            if not reference_data or reference_data.get("DELETE"):
                continue
            CustomerReference.objects.create(
                customer=customer,
                reference_name=reference_data["reference_name"],
                reference_mobile=reference_data["reference_mobile"],
                reference_address=reference_data["reference_address"],
                relationship=reference_data["relationship"],
            )

        bank_detail = bank_form.save(commit=False)
        bank_detail.customer = customer
        bank_detail.save()

        for document_data in document_formset.cleaned_data:
            if not document_data or not document_data.get("document_type"):
                continue
            CustomerDocument.objects.create(
                customer=customer,
                document_type=document_data["document_type"],
                document_number=document_data.get("document_number", ""),
                file=document_data.get("file"),
                remarks=document_data.get("remarks", ""),
            )

        category = personal_form.cleaned_data.get("customer_category")
        if category == PersonalDetailsForm.CATEGORY_GROUP:
            messages.success(
                self.request,
                f"Customer {customer.customer_id} created. Next, add them to a "
                f"loan group when you create their loan.",
            )
        else:
            messages.success(
                self.request,
                f"Customer {customer.customer_id} created. You can now create "
                f"an individual loan for them.",
            )
        return redirect(reverse("customers:detail", args=[customer.pk]))


@login_required
def customer_list(request):
    search_form = CustomerSearchForm(request.GET or None)
    customers = Customer.objects.all()

    if search_form.is_valid():
        query = search_form.cleaned_data.get("q")
        status = search_form.cleaned_data.get("status")
        created_from = search_form.cleaned_data.get("created_from")
        created_to = search_form.cleaned_data.get("created_to")
        location = search_form.cleaned_data.get("location")

        if query:
            customers = customers.filter(
                Q(customer_id__icontains=query)
                | Q(full_name__icontains=query)
                | Q(mobile__icontains=query)
                | Q(loans__loan_number__icontains=query)
            ).distinct()
        if status:
            customers = customers.filter(status=status)
        if created_from:
            customers = customers.filter(created_at__date__gte=created_from)
        if created_to:
            customers = customers.filter(created_at__date__lte=created_to)
        if location:
            customers = customers.filter(
                Q(permanent_city__icontains=location)
                | Q(permanent_district__icontains=location)
                | Q(permanent_state__icontains=location)
            )

    sort = request.GET.get("sort", "-created_at")
    allowed_sorts = {"customer_id", "full_name", "-created_at", "created_at"}
    if sort in allowed_sorts:
        customers = customers.order_by(sort)

    paginator = Paginator(customers, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Computed per-page (not for the whole table) so this stays cheap —
    # active loan count and outstanding are properties derived from
    # Installment data, not simple DB columns to aggregate directly.
    for customer in page_obj:
        active_loans = list(customer.loans.filter(status="active"))
        customer.active_loan_count = len(active_loans)
        customer.total_outstanding_amount = sum(
            (loan.total_outstanding for loan in active_loans), start=Decimal("0")
        )

    return render(
        request,
        "customers/customer_list.html",
        {"page_obj": page_obj, "search_form": search_form, "sort": sort},
    )


class CustomerDetailView(LoginRequiredMixin, DetailView):
    """Profile page with tabs: Overview / Personal / Address / Reference /
    Bank / Documents — matches §13 of the spec."""

    model = Customer
    template_name = "customers/customer_detail.html"
    context_object_name = "customer"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.object
        context["references"] = customer.references.all()
        context["documents"] = customer.documents.filter(is_archived=False).select_related("document_type")
        context["bank_detail"] = getattr(customer, "bank_detail", None)
        context["active_tab"] = self.request.GET.get("tab", "overview")
        context["loans"] = customer.loans.all()
        context["active_loan_count"] = customer.loans.filter(status="active").count()
        context["total_outstanding_amount"] = sum(
            (loan.total_outstanding for loan in customer.loans.filter(status="active")),
            start=Decimal("0"),
        )
        return context


class CustomerUpdateView(LoginRequiredMixin, UpdateView):
    """Edits an existing customer. Uses one combined page rather than the
    wizard — all the data already exists, so there is no benefit to
    forcing a fresh multi-step walk-through for a correction."""

    model = Customer
    form_class = PersonalDetailsForm
    template_name = "customers/customer_edit.html"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields.pop("customer_category", None)
        return form

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == "POST":
            context["address_form"] = AddressForm(self.request.POST, instance=self.object)
        else:
            context["address_form"] = AddressForm(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        address_form = context["address_form"]
        if not address_form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        with transaction.atomic():
            customer = form.save(commit=False)
            for field_name, value in address_form.cleaned_data.items():
                setattr(customer, field_name, value)
            customer.full_clean(exclude=["customer_id"])
            customer.save()
        messages.success(self.request, f"Customer {customer.customer_id} updated.")
        return redirect(reverse("customers:detail", args=[customer.pk]))


@login_required
def add_customer_document(request, pk):
    """Adds a single extra KYC document to an existing customer, e.g. if
    one was missed at creation time or needs replacing."""
    customer = get_object_or_404(Customer, pk=pk)
    from .forms import DocumentForm

    if request.method == "POST":
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid() and form.cleaned_data.get("document_type"):
            CustomerDocument.objects.create(
                customer=customer,
                document_type=form.cleaned_data["document_type"],
                document_number=form.cleaned_data.get("document_number", ""),
                file=form.cleaned_data.get("file"),
                remarks=form.cleaned_data.get("remarks", ""),
            )
            messages.success(request, "Document added.")
            return redirect(f"{reverse('customers:detail', args=[pk])}?tab=documents")
    else:
        form = DocumentForm()
    return render(
        request, "customers/customer_document_form.html", {"form": form, "customer": customer}
    )


@login_required
def verify_customer_document(request, pk, document_id):
    document = get_object_or_404(CustomerDocument, pk=document_id, customer_id=pk)
    new_status = request.POST.get("verified_status")
    if request.method == "POST" and new_status in {
        CustomerDocument.STATUS_PENDING,
        CustomerDocument.STATUS_VERIFIED,
        CustomerDocument.STATUS_REJECTED,
    }:
        document.verified_status = new_status
        from django.utils import timezone

        document.verified_date = timezone.localdate() if new_status != CustomerDocument.STATUS_PENDING else None
        document.save(update_fields=["verified_status", "verified_date"])
        messages.success(request, f"Document marked as {new_status}.")
    return redirect(f"{reverse('customers:detail', args=[pk])}?tab=documents")
