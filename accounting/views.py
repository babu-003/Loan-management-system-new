from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from .forms import (
    LedgerAccountForm,
    VoucherCategoryForm,
    VoucherForm,
)

from .models import (
    LedgerAccount,
    Voucher,
    VoucherCategory,
    VoucherEntry,
    create_voucher,
    ensure_category_account,
    get_bank_account,
    get_cash_account,
)


@login_required
def dashboard(request):

    vouchers = (
        Voucher.objects
        .select_related("category")[:10]
    )

    cash = get_cash_account().balance

    bank = get_bank_account().balance

    total_debit = (
        VoucherEntry.objects
        .aggregate(v=Sum("debit"))["v"]
        or 0
    )

    total_credit = (
        VoucherEntry.objects
        .aggregate(v=Sum("credit"))["v"]
        or 0
    )

    return render(
        request,
        "accounting/dashboard.html",
        {
            "vouchers": vouchers,
            "cash_balance": cash,
            "bank_balance": bank,
            "total_debit": total_debit,
            "total_credit": total_credit,
        },
    )


@login_required
def voucher_list(request):

    qs = (
        Voucher.objects
        .select_related("category")
    )

    paginator = Paginator(
        qs,
        30
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    return render(
        request,
        "accounting/voucher_list.html",
        {
            "page_obj": page_obj
        }
    )


@login_required
def voucher_add(request):

    if request.method == "POST":

        form = VoucherForm(
            request.POST
        )

        if form.is_valid():

            cd = form.cleaned_data

            category = cd["category"]

            category_account = (
                ensure_category_account(
                    category
                )
            )

            if (
                cd["payment_mode"]
                == Voucher.MODE_CASH
            ):

                source_account = (
                    get_cash_account()
                )

            else:

                source_account = (
                    get_bank_account()
                )

            payment_mode_display = dict(
                Voucher.MODE_CHOICES
            ).get(
                cd["payment_mode"],
                cd["payment_mode"]
            )

            if (
                cd["voucher_type"]
                == Voucher.TYPE_EXPENSE
            ):

                debit_account = (
                    category_account
                )

                credit_account = (
                    source_account
                )

                default_narration = (
                    f"Being {category.name} "
                    f"paid via "
                    f"{payment_mode_display}."
                )

            elif (
                cd["voucher_type"]
                == Voucher.TYPE_INVESTMENT
            ):

                debit_account = (
                    category_account
                )

                credit_account = (
                    source_account
                )

                default_narration = (
                    f"Being {category.name} "
                    f"investment purchased via "
                    f"{payment_mode_display}."
                )

            else:

                debit_account = (
                    source_account
                )

                credit_account = (
                    category_account
                )

                default_narration = (
                    f"Being {category.name} "
                    f"received via "
                    f"{payment_mode_display}."
                )

            narration = (
                cd["narration"].strip()
                or default_narration
            )

            voucher = create_voucher(
                voucher_type=cd["voucher_type"],
                amount=cd["amount"],
                debit_account=debit_account,
                credit_account=credit_account,
                voucher_date=cd["voucher_date"],
                payment_mode=cd["payment_mode"],
                transaction_id=cd["transaction_id"],
                category=category,
                narration=narration,
                party_name="",
            )

            messages.success(
                request,
                f"Voucher {voucher.voucher_number} created."
            )

            return redirect(
                "accounting:voucher_detail",
                pk=voucher.pk
            )

    else:

        form = VoucherForm(
            initial={
                "voucher_type":
                    Voucher.TYPE_EXPENSE
            }
        )

    return render(
        request,
        "accounting/voucher_form.html",
        {
            "form": form
        }
    )


@login_required
def voucher_detail(request, pk):

    voucher = get_object_or_404(
        Voucher.objects.prefetch_related(
            "entries__ledger_account"
        ),
        pk=pk
    )

    return render(
        request,
        "accounting/voucher_detail.html",
        {
            "voucher": voucher
        }
    )

@login_required
def download_voucher(request, pk):
    voucher = get_object_or_404(
        Voucher.objects.prefetch_related("entries__ledger_account"),
        pk=pk
    )

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "VoucherTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=20,
        spaceAfter=6,
    )

    subtitle_style = ParagraphStyle(
        "VoucherSubtitle",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=10,
        textColor=colors.grey,
        spaceAfter=18,
    )

    normal_style = ParagraphStyle(
        "VoucherNormal",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
    )

    heading_style = ParagraphStyle(
        "VoucherHeading",
        parent=styles["Heading2"],
        fontSize=12,
        spaceBefore=8,
        spaceAfter=8,
    )

    story = []

    # Header
    story.append(Paragraph("ACCOUNTING VOUCHER", title_style))
    story.append(
        Paragraph(
            f"Voucher No: <b>{voucher.voucher_number}</b>",
            subtitle_style
        )
    )

    # Voucher information
    voucher_info = [
        [
            Paragraph("<b>Voucher Type</b>", normal_style),
            Paragraph(voucher.get_voucher_type_display(), normal_style),
            Paragraph("<b>Date</b>", normal_style),
            Paragraph(voucher.voucher_date.strftime("%d-%m-%Y"), normal_style),
        ],
        [
            Paragraph("<b>Amount</b>", normal_style),
            Paragraph(f"Rs. {voucher.amount:,.2f}", normal_style),
            Paragraph("<b>Payment Mode</b>", normal_style),
            Paragraph(voucher.get_payment_mode_display(), normal_style),
        ],
    ]

    if voucher.transaction_id:
        voucher_info.append(
            [
                Paragraph("<b>Transaction ID</b>", normal_style),
                Paragraph(voucher.transaction_id, normal_style),
                Paragraph("<b>Party</b>", normal_style),
                Paragraph(voucher.party_name or "—", normal_style),
            ]
        )
    else:
        voucher_info.append(
            [
                Paragraph("<b>Party</b>", normal_style),
                Paragraph(voucher.party_name or "—", normal_style),
                Paragraph("", normal_style),
                Paragraph("", normal_style),
            ]
        )

    info_table = Table(
        voucher_info,
        colWidths=[32 * mm, 55 * mm, 35 * mm, 55 * mm],
    )

    info_table.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
            ("BACKGROUND", (2, 0), (2, -1), colors.whitesmoke),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ])
    )

    story.append(info_table)
    story.append(Spacer(1, 12))

    # Category
    if voucher.category:
        story.append(
            Paragraph(
                f"<b>Category:</b> {voucher.category.name}",
                normal_style
            )
        )
        story.append(Spacer(1, 8))

    # Debit / Credit
    story.append(Paragraph("Debit / Credit", heading_style))

    entry_data = [
        [
            Paragraph("<b>Ledger Account</b>", normal_style),
            Paragraph("<b>Debit</b>", normal_style),
            Paragraph("<b>Credit</b>", normal_style),
        ]
    ]

    for entry in voucher.entries.all():
        debit = f"Rs. {entry.debit:,.2f}" if entry.debit else "—"
        credit = f"Rs. {entry.credit:,.2f}" if entry.credit else "—"

        entry_data.append([
            Paragraph(entry.ledger_account.name, normal_style),
            Paragraph(debit, normal_style),
            Paragraph(credit, normal_style),
        ])

    entry_data.append([
        Paragraph("<b>Total</b>", normal_style),
        Paragraph(f"<b>Rs. {voucher.amount:,.2f}</b>", normal_style),
        Paragraph(f"<b>Rs. {voucher.amount:,.2f}</b>", normal_style),
    ])

    entry_table = Table(
        entry_data,
        colWidths=[105 * mm, 35 * mm, 35 * mm],
    )

    entry_table.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ])
    )

    story.append(entry_table)
    story.append(Spacer(1, 15))

    # Narration
    story.append(Paragraph("Narration", heading_style))
    story.append(
        Paragraph(
            voucher.narration or "—",
            normal_style
        )
    )

    story.append(Spacer(1, 30))

    story.append(
        Paragraph(
            "This is a system-generated accounting voucher.",
            ParagraphStyle(
                "Footer",
                parent=normal_style,
                alignment=TA_CENTER,
                textColor=colors.grey,
                fontSize=8,
            )
        )
    )

    document.build(story)

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(
        pdf,
        content_type="application/pdf"
    )

    response["Content-Disposition"] = (
        f'attachment; filename="Voucher-{voucher.voucher_number}.pdf"'
    )

    return response

@login_required
def ledger_list(request):
    accounts = LedgerAccount.objects.filter(is_active=True).order_by("name")

    grouped_accounts = {
        "Cash & Bank": accounts.filter(
            account_type__in=[
                LedgerAccount.TYPE_CASH,
                LedgerAccount.TYPE_BANK,
            ]
        ),
        "Customers": accounts.filter(
            account_type=LedgerAccount.TYPE_CUSTOMER
        ),
        "Expenses": accounts.filter(
            account_type=LedgerAccount.TYPE_EXPENSE
        ),
        "Investments": accounts.filter(
            account_type=LedgerAccount.TYPE_INVESTMENT
        ),
        "Income": accounts.filter(
            account_type=LedgerAccount.TYPE_INCOME
        ),
        "Borrowing": accounts.filter(
            account_type=LedgerAccount.TYPE_BORROWING
        ),
        "Other": accounts.filter(
            account_type=LedgerAccount.TYPE_OTHER
        ),
    }

    form = LedgerAccountForm()

    return render(
        request,
        "accounting/ledger_list.html",
        {
            "accounts": accounts,
            "grouped_accounts": grouped_accounts,
            "form": form,
        },
    )

@login_required
def ledger_detail(request, pk):

    account = get_object_or_404(
        LedgerAccount,
        pk=pk
    )

    entries = (
        account.entries
        .select_related("voucher")
        .order_by(
            "voucher__voucher_date",
            "voucher__created_at"
        )
    )

    return render(
        request,
        "accounting/ledger_detail.html",
        {
            "account": account,
            "entries": entries
        }
    )


@login_required
def category_list(request):

    categories = (
        VoucherCategory.objects
        .select_related("ledger_account")
        .all()
    )

    if request.method == "POST":

        form = VoucherCategoryForm(
            request.POST
        )

        if form.is_valid():

            category = form.save()

            if category.voucher_type in {
                VoucherCategory.TYPE_EXPENSE,
                VoucherCategory.TYPE_INVESTMENT,
                VoucherCategory.TYPE_INCOME,
            }:

                ensure_category_account(
                    category
                )

            messages.success(
                request,
                "Voucher category added."
            )

            return redirect(
                "accounting:categories"
            )

    else:

        form = VoucherCategoryForm()

    return render(
        request,
        "accounting/categories.html",
        {
            "categories": categories,
            "form": form
        }
    )