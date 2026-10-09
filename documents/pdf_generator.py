import io
import re
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from xhtml2pdf import pisa

from core.models import get_setting

from .i18n import frequency_label, notice_title, tr

PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")
FONT_DIR = Path(__file__).resolve().parent / "fonts"


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
        "first_due_date", "today_date",
    ]
    if category == "notice":
        return common + ["notice_type", "notice_date", "notice_reason", "overdue_count", "overdue_amount"]
    if category == "closing":
        return common + ["closing_date"]
    return common


def build_loan_context(loan, lang="en"):
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
        "repayment_frequency": frequency_label(lang, loan.get_repayment_frequency_display()),
        "start_date": loan.start_date,
        "first_due_date": loan.first_due_date,
        "today_date": timezone.localdate(),
        "lang": lang,
    }


def build_notice_context(loan, notice, lang="en"):
    context = build_loan_context(loan, lang)
    overdue_installments = loan.installments.filter(
        due_date__lt=timezone.localdate()
    ).exclude(status="paid")
    overdue_amount = sum((i.balance_amount for i in overdue_installments), start=0)
    context.update({
        "notice_type": notice_title(lang, notice.notice_type.name),
        "notice_date": notice.notice_date,
        "notice_reason": notice.reason,
        "overdue_count": overdue_installments.count(),
        "overdue_amount": overdue_amount,
    })
    return context


def build_closing_context(loan, lang="en"):
    context = build_loan_context(loan, lang)
    context.update({
        "closing_date": loan.closing_date or timezone.localdate(),
    })
    return context


def document_title(category, lang, notice=None):
    if category == "agreement":
        return tr(lang, "title_agreement")
    if category == "closing":
        return tr(lang, "title_closing")
    return notice_title(lang, notice.notice_type.name) if notice else tr(lang, "title_notice_fallback")


def details_table_for(category, context, lang="en"):
    """The fixed, non-editable summary table shown above the admin's
    editable text on every generated document — so key figures (amount,
    dates, installment count) are always present even if the editable
    text below is trimmed or reworded.

    No 'total payable' / 'total paid' row on any document, and no
    interest row on the notice."""
    rs = tr(lang, "rs")
    rows = [
        (tr(lang, "loan_no"), context.get("loan_number")),
        (tr(lang, "customer_name"), context.get("customer_name")),
        (tr(lang, "principal_amount"), f"{rs} {context.get('principal_amount')}"),
    ]
    rows += [
        (tr(lang, "installments"), context.get("number_of_installments")),
        (tr(lang, "frequency"), context.get("repayment_frequency")),
        (tr(lang, "start_date"), context.get("start_date")),
    ]
    if category == "notice":
        rows += [
            (tr(lang, "overdue_installments"), context.get("overdue_count")),
            (tr(lang, "notice_date"), context.get("notice_date")),
        ]
    if category == "closing":
        rows += [
            (tr(lang, "principal_returned"), f"{rs} {context.get('principal_amount')}"),
            (tr(lang, "closing_date"), context.get("closing_date")),
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


def _split_paragraphs(text):
    return [p.strip() for p in re.split(r"\n\s*\n", (text or "").strip()) if p.strip()]


def _paragraphs_for_pdf(text):
    """Splits admin-edited text into real <p> elements (one per blank-line
    -separated paragraph), converting single line breaks within a
    paragraph into <br/>."""
    from django.utils.safestring import mark_safe

    return [
        mark_safe(_escape_for_pdf(paragraph).replace("\n", "<br/>"))
        for paragraph in _split_paragraphs(text)
    ]


def render_pdf(title, details_rows, body_text, context, lang="en"):
    if lang == "ta":
        return _render_pdf_tamil(title, details_rows, body_text, context)
    return _render_pdf_english(title, details_rows, body_text, context)


def _render_pdf_english(title, details_rows, body_text, context):
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


# ---------------------------------------------------------------------------
# Tamil PDFs
#
# xhtml2pdf (ReportLab) draws Unicode characters one by one and does no
# OpenType shaping, which Tamil needs (vowel signs such as ெ ே ை move to
# the left of the consonant, and ொ ோ ௌ are split around it). Tamil text
# through xhtml2pdf comes out with vowel signs in the wrong place. So
# Tamil documents are laid out with fpdf2, which shapes text through
# HarfBuzz (needs: pip install fpdf2 uharfbuzz).
# ---------------------------------------------------------------------------

def _first_existing(paths):
    for path in paths:
        if path and Path(path).is_file():
            return str(path)
    return None


def _find_tamil_fonts():
    """(regular, bold) font files that contain Tamil. Order: explicit
    settings, then documents/fonts/ (drop Noto Sans Tamil in there for
    the best look), then fonts commonly installed with the OS."""
    s_reg = getattr(settings, "TAMIL_FONT_REGULAR", None)
    s_bold = getattr(settings, "TAMIL_FONT_BOLD", None)
    pairs = [
        (s_reg, s_bold),
        (FONT_DIR / "NotoSansTamil-Regular.ttf", FONT_DIR / "NotoSansTamil-Bold.ttf"),
        (r"C:\Windows\Fonts\nirmala.ttf", r"C:\Windows\Fonts\nirmalab.ttf"),
        (r"C:\Windows\Fonts\latha.ttf", r"C:\Windows\Fonts\lathab.ttf"),
        ("/usr/share/fonts/truetype/noto/NotoSansTamil-Regular.ttf",
         "/usr/share/fonts/truetype/noto/NotoSansTamil-Bold.ttf"),
        (FONT_DIR / "FreeSerif.ttf", FONT_DIR / "FreeSerifBold.ttf"),
    ]
    for regular, bold in pairs:
        if regular and Path(regular).is_file():
            return str(regular), _first_existing([bold]) or str(regular)
    raise RuntimeError(
        "No Tamil font found. Put NotoSansTamil-Regular.ttf and "
        "NotoSansTamil-Bold.ttf in documents/fonts/ (or set "
        "TAMIL_FONT_REGULAR / TAMIL_FONT_BOLD in settings)."
    )


def _find_latin_fonts():
    """Optional (regular, bold) used only for letters the Tamil font
    doesn't have (English names/addresses)."""
    pairs = [
        (FONT_DIR / "NotoSans-Regular.ttf", FONT_DIR / "NotoSans-Bold.ttf"),
        (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        (FONT_DIR / "FreeSerif.ttf", FONT_DIR / "FreeSerifBold.ttf"),
    ]
    for regular, bold in pairs:
        if Path(regular).is_file():
            return str(regular), _first_existing([bold]) or str(regular)
    return None


def _render_pdf_tamil(title, details_rows, body_text, context):
    from fpdf import FPDF
    from fpdf.fonts import FontFace

    lang = "ta"
    regular, bold = _find_tamil_fonts()

    pdf = FPDF(format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_font("TamilDoc", "", regular)
    pdf.add_font("TamilDoc", "B", bold)
    latin = _find_latin_fonts()
    if latin and latin[0] != regular:
        pdf.add_font("LatinDoc", "", latin[0])
        pdf.add_font("LatinDoc", "B", latin[1])
        pdf.set_fallback_fonts(["LatinDoc"])
    pdf.set_text_shaping(True)
    pdf.add_page()

    # Letterhead
    pdf.set_font("TamilDoc", "B", 15)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(0, 8, str(context.get("company_name") or ""), align="C", new_x="LMARGIN", new_y="NEXT")
    contact = [str(context.get("company_address") or "")]
    if context.get("company_phone"):
        contact.append(f"{tr(lang, 'phone_prefix')} {context['company_phone']}")
    if context.get("company_email"):
        contact.append(str(context["company_email"]))
    pdf.set_font("TamilDoc", "", 9)
    pdf.set_text_color(107, 114, 128)
    pdf.multi_cell(0, 5, "  |  ".join(part for part in contact if part), align="C",
                   new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(29, 78, 216)
    pdf.set_line_width(0.6)
    y = pdf.get_y() + 1
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.set_y(y + 5)

    # Title
    pdf.set_text_color(31, 41, 55)
    pdf.set_font("TamilDoc", "B", 13)
    pdf.cell(0, 8, str(title), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Details table
    pdf.set_font("TamilDoc", "", 10)
    pdf.set_draw_color(209, 213, 219)
    pdf.set_line_width(0.2)
    label_style = FontFace(emphasis="BOLD", fill_color=(244, 246, 248))
    with pdf.table(col_widths=(40, 60), first_row_as_headings=False, line_height=6.5) as table:
        for label, value in details_rows:
            row = table.row()
            row.cell(str(label), style=label_style)
            row.cell("" if value is None else str(value))
    pdf.ln(6)

    # Body text
    pdf.set_font("TamilDoc", "", 10.5)
    for paragraph in _split_paragraphs(body_text):
        pdf.multi_cell(0, 6.5, paragraph, align="L", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2.5)

    # Signatures
    if pdf.get_y() > pdf.h - 60:
        pdf.add_page()
    pdf.ln(18)
    half = (pdf.w - pdf.l_margin - pdf.r_margin) / 2
    pdf.set_font("TamilDoc", "", 9.5)
    pdf.cell(half - 4, 7, tr(lang, "signatory"), border="T", new_x="RIGHT", new_y="TOP")
    pdf.cell(8, 7, "", new_x="RIGHT", new_y="TOP")
    pdf.cell(half - 4, 7, tr(lang, "borrower_signature"), border="T", align="R",
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(half, 6, str(context.get("company_name") or ""), new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
