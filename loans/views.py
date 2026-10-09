from decimal import Decimal
import math
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import InstallmentDueDateForm, LoanForm, LoanGroupForm, LoanSearchForm , LoanGroupMemberForm
from .models import Installment, Loan, LoanGroup,LoanGroupMember

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
def loan_create(request, group_pk=None):
    initial = {}

    customer_id = request.GET.get("customer")
    group_id = request.GET.get("group")

    group = None

    # Group-specific Add Loan URL
    if group_pk:
        group = get_object_or_404(
            LoanGroup,
            pk=group_pk,
            status=LoanGroup.STATUS_ACTIVE,
        )

    # Group selected through the normal Add Loan page
    elif group_id:
        group = get_object_or_404(
            LoanGroup,
            pk=group_id,
            status=LoanGroup.STATUS_ACTIVE,
        )

    if group:
        initial["loan_group"] = group.pk

    if customer_id:
        initial["customer"] = customer_id

    if request.method == "POST":
        # Only show customers belonging to the selected group
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

            messages.success(
                request,
                f"Loan {loan.loan_number} created with "
                f"{loan.number_of_installments} installments.",
            )

            return redirect("loans:detail", pk=loan.pk)

    else:
        form = LoanForm(initial=initial, group=group)

    return render(
        request,
        "loans/loan_form.html",
        {
            "form": form,
            "group": group,
        },
    )



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
def repayment_card_pdf(request, pk):
    """Download a printable customer repayment card for this loan."""
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    loan = get_object_or_404(
        Loan.objects.select_related("customer", "loan_type", "interest_type"), pk=pk
    )
    installments = list(loan.installments.all().order_by("installment_number"))
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=14 * mm, leftMargin=14 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
        title=f"Repayment Card - {loan.loan_number}",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="CardTitle", parent=styles["Title"], fontSize=16, leading=20,
        alignment=TA_CENTER, spaceAfter=5 * mm,
    ))
    styles.add(ParagraphStyle(
        name="SmallInfo", parent=styles["Normal"], fontSize=9, leading=13,
    ))
    story = [Paragraph("CUSTOMER LOAN REPAYMENT CARD", styles["CardTitle"])]

    customer = loan.customer
    info_rows = [
        [Paragraph(f"<b>Customer:</b> {customer.full_name}", styles["SmallInfo"]),
         Paragraph(f"<b>Customer ID:</b> {customer.customer_id}", styles["SmallInfo"])],
        [Paragraph(f"<b>Mobile:</b> {customer.mobile}", styles["SmallInfo"]),
         Paragraph(f"<b>Loan No.:</b> {loan.loan_number}", styles["SmallInfo"])],
        [Paragraph(f"<b>Principal:</b> ₹{loan.principal_amount:,.2f}", styles["SmallInfo"]),
         Paragraph(f"<b>Installments:</b> {loan.number_of_installments}", styles["SmallInfo"])],
    ]
    info = Table(info_rows, colWidths=[88 * mm, 88 * mm])
    info.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.lightgrey),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([info, Spacer(1, 5 * mm)])

    data = [["Installment", "Due Date", "Principal Amount (₹)", "Amount Paid (₹)", "Customer Signature"]]
    for inst in installments:
        data.append([
            str(inst.installment_number),
            inst.due_date.strftime("%d-%m-%Y"),
            f"{inst.principal_component:,.2f}",
            "",  # left blank for manual entry by collector/customer
            "",  # left blank for handwritten signature
        ])
    if not installments:
        data.append(["No installments generated", "", "", "", ""])

    schedule = Table(
        data,
        colWidths=[23 * mm, 30 * mm, 39 * mm, 37 * mm, 47 * mm],
        repeatRows=1,
        rowHeights=[11 * mm] + [13 * mm] * max(len(data) - 1, 1),
    )
    schedule.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9eef5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 1), (3, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.65, colors.black),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(schedule)
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(
        "Keep this card safely. Write the amount received and sign for each installment when payment is collected.",
        styles["SmallInfo"],
    ))
    doc.build(story)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="repayment_card_{loan.loan_number}.pdf"'
    return response


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
@transaction.atomic
def loan_group_add_member(request, pk):
    group = get_object_or_404(LoanGroup, pk=pk, status=LoanGroup.STATUS_ACTIVE)
    if request.method == "POST":
        form = LoanGroupMemberForm(request.POST, group=group)
        if form.is_valid():
            member = LoanGroupMember.objects.create(
                group=group,
                customer=form.cleaned_data["customer"],
            )
            messages.success(
                request,
                f"{member.customer.full_name} added to {group.group_id}. Now create their loan.",
            )
            return redirect(
                f"{reverse('loans:add')}?group={group.pk}&customer={member.customer.pk}"
            )
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


@login_required
def loan_delete(request, pk):
    """Password-confirmed loan deletion. Loans with recorded payments are
    blocked to preserve financial history and payment/audit integrity.
    """
    loan = get_object_or_404(Loan.objects.select_related("customer"), pk=pk)
    has_payments = loan.payments.exists()

    if request.method == "POST":
        if has_payments:
            messages.error(
                request,
                "This loan has recorded payments and cannot be deleted. "
                "Preserve its financial history instead of deleting it.",
            )
            return redirect(f"{reverse('customers:detail', args=[loan.customer_id])}?tab=loans")

        password = request.POST.get("password", "")
        if not password or not request.user.check_password(password):
            messages.error(request, "Incorrect login password. The loan was not deleted.")
            return render(
                request, "loans/loan_delete_confirm.html",
                {"loan": loan, "has_payments": has_payments}, status=400,
            )

        customer_id = loan.customer_id
        loan_label = loan.loan_number
        try:
            loan.delete()
        except ProtectedError:
            messages.error(
                request,
                "This loan is linked to protected financial records and cannot be deleted.",
            )
            return redirect(f"{reverse('customers:detail', args=[customer_id])}?tab=loans")

        messages.success(request, f"Loan {loan_label} was deleted.")
        return redirect(f"{reverse('customers:detail', args=[customer_id])}?tab=loans")

    return render(
        request, "loans/loan_delete_confirm.html",
        {"loan": loan, "has_payments": has_payments},
    )
