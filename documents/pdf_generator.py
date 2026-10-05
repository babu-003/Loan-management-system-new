import io
import re

from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa

from core.models import get_setting

PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def render_placeholders(text, context):
    """Simple, safe {{ field_name }} substitution — deliberately NOT the
    full Django template engine, so admins editing this text can't
    accidentally (or otherwise) reach template tags/filters, just plain
    fill-in-the-blanks. Unknown placeholders are left as-is rather than
    silently blanked, so a typo is obvious instead of invisible."""
    def replace(match):
        key = match.group(1)
        return str(context.get(key, match.group(0)))
    return PLACEHOLDER_PATTERN.sub(replace, text)


def available_placeholders(category):
    common = [
        "company_name", "company_address", "company_phone", "company_email",
        "customer_name", "customer_address", "customer_mobile",
        "loan_number", "principal_amount", "interest_rate", "interest_type",
        "number_of_installments", "repayment_frequency", "start_date",
        "first_due_date", "total_payable", "total_interest", "today_date",
    ]
    if category == "notice":
        return common + ["notice_type", "notice_date", "notice_reason", "overdue_count", "overdue_amount"]
    if category == "closing":
        return common + ["closing_date", "total_paid"]
    return common


def build_loan_context(loan):
    customer = loan.customer
    return {
        "company_name": get_setting("company_name") or "",
        "company_address": get_setting("company_address") or "",
        "company_phone": get_setting("company_phone") or "",
        "company_email": get_setting("company_email") or "",
        "customer_name": customer.full_name,
        "customer_address": f"{customer.permanent_door_no}, {customer.permanent_street}, "
                             f"{customer.permanent_city}, {customer.permanent_district}, "
                             f"{customer.permanent_state} - {customer.permanent_pincode}",
        "customer_mobile": customer.mobile,
        "loan_number": loan.loan_number,
        "principal_amount": loan.principal_amount,
        "interest_rate": loan.interest_rate,
        "interest_type": loan.interest_type.name,
        "number_of_installments": loan.number_of_installments,
        "repayment_frequency": loan.get_repayment_frequency_display(),
        "start_date": loan.start_date,
        "first_due_date": loan.first_due_date,
        "total_payable": loan.total_payable,
        "total_interest": loan.total_interest,
        "today_date": timezone.localdate(),
    }


def build_notice_context(loan, notice):
    context = build_loan_context(loan)
    overdue_installments = loan.installments.filter(
        due_date__lt=timezone.localdate()
    ).exclude(status="paid")
    overdue_amount = sum((i.balance_amount for i in overdue_installments), start=0)
    context.update({
        "notice_type": notice.notice_type.name,
        "notice_date": notice.notice_date,
        "notice_reason": notice.reason,
        "overdue_count": overdue_installments.count(),
        "overdue_amount": overdue_amount,
    })
    return context


def build_closing_context(loan):
    context = build_loan_context(loan)
    context.update({
        "closing_date": loan.closing_date or timezone.localdate(),
        "total_paid": loan.total_paid,
    })
    return context


def details_table_for(category, context):
    """The fixed, non-editable summary table shown above the admin's
    editable text on every generated document — so key figures (amount,
    dates, installment count) are always present even if the editable
    text below is trimmed or reworded."""
    rows = [
        ("Loan No.", context.get("loan_number")),
        ("Customer Name", context.get("customer_name")),
        ("Principal Amount", f"Rs. {context.get('principal_amount')}"),
        ("Interest Rate", f"{context.get('interest_rate')}% p.a."),
        ("Number of Installments", context.get("number_of_installments")),
        ("Repayment Frequency", context.get("repayment_frequency")),
        ("Start Date", context.get("start_date")),
        ("Total Payable", f"Rs. {context.get('total_payable')}"),
    ]
    if category == "notice":
        rows += [
            ("Overdue Installments", context.get("overdue_count")),
            ("Overdue Amount", f"Rs. {context.get('overdue_amount')}"),
            ("Notice Date", context.get("notice_date")),
        ]
    if category == "closing":
        rows += [
            ("Total Paid", f"Rs. {context.get('total_paid')}"),
            ("Closing Date", context.get("closing_date")),
        ]
    return rows


def _escape_for_pdf(text):
    """Escapes only the characters that could break the HTML structure
    (< > &) — deliberately NOT using Django's full auto-escaping, which
    also converts quote characters to &quot;/&#39; entities. xhtml2pdf
    doesn't reliably decode those back into visible characters, so any
    quote marks in admin-edited text (e.g. "Lender", "Borrower") would
    show up literally as the entity text instead of a printable quote.
    Plain quote characters inside HTML text (not inside an attribute)
    are already safe without escaping."""
    if text is None:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _paragraphs_for_pdf(text):
    """Splits admin-edited text into real <p> elements (one per blank-line
    -separated paragraph), converting single line breaks within a
    paragraph into <br/>. This replaces relying on CSS white-space:
    pre-wrap for layout — safer and more predictable across xhtml2pdf's
    line-wrapping, and it's what actually fixes body text running past
    the page margin instead of wrapping."""
    from django.utils.safestring import mark_safe

    escaped = _escape_for_pdf(text)
    raw_paragraphs = re.split(r"\n\s*\n", escaped.strip())
    return [
        mark_safe(paragraph.strip().replace("\n", "<br/>"))
        for paragraph in raw_paragraphs if paragraph.strip()
    ]


def render_pdf(title, details_rows, body_text, context):
    from django.utils.safestring import mark_safe

    html = render_to_string("documents/pdf_document.html", {
        "title": mark_safe(_escape_for_pdf(title)),
        "details_rows": [
            (mark_safe(_escape_for_pdf(label)), mark_safe(_escape_for_pdf(value)))
            for label, value in details_rows
        ],
        "body_paragraphs": _paragraphs_for_pdf(body_text),
        "company_name": mark_safe(_escape_for_pdf(context.get("company_name"))),
        "company_address": mark_safe(_escape_for_pdf(context.get("company_address"))),
        "company_phone": mark_safe(_escape_for_pdf(context.get("company_phone"))),
        "company_email": mark_safe(_escape_for_pdf(context.get("company_email"))),
    })
    buffer = io.BytesIO()
    pisa.CreatePDF(html, dest=buffer)
    return buffer.getvalue()
