from django.db import migrations

AGREEMENT_DEFAULT = """This Loan Agreement is made on {{ today_date }} between {{ company_name }}, having its office at {{ company_address }} (hereinafter referred to as the "Lender"), and {{ customer_name }}, residing at {{ customer_address }}, mobile number {{ customer_mobile }} (hereinafter referred to as the "Borrower").

The Lender agrees to lend, and the Borrower agrees to borrow, a sum of Rs. {{ principal_amount }} (Loan No. {{ loan_number }}) at an interest rate of {{ interest_rate }}% per annum, calculated on a {{ interest_type }} basis.

The loan shall be repaid in {{ number_of_installments }} {{ repayment_frequency }} installments, commencing from {{ first_due_date }}. The total amount payable, including interest, is Rs. {{ total_payable }}.

The Borrower agrees to repay each installment on or before its due date. Failure to pay any installment may result in the Lender issuing a formal notice and taking appropriate recovery action as per applicable law.

Both parties have read and understood the terms of this agreement and agree to be bound by them."""

NOTICE_DEFAULT = """To,
{{ customer_name }}
{{ customer_address }}

Subject: {{ notice_type }} regarding overdue payment on Loan No. {{ loan_number }}

Dear {{ customer_name }},

This is to bring to your attention that your loan account (Loan No. {{ loan_number }}) with {{ company_name }} currently has {{ overdue_count }} overdue installment(s) totaling Rs. {{ overdue_amount }}.

Reason: {{ notice_reason }}

You are hereby requested to clear the overdue amount at the earliest to avoid further action. Please contact us at {{ company_phone }} or visit our office at {{ company_address }} to settle the dues or discuss a repayment plan.

Failure to respond to this notice may result in further recovery action as per the terms of your loan agreement.

Regards,
{{ company_name }}"""

CLOSING_DEFAULT = """This is to certify that the loan bearing Loan No. {{ loan_number }} issued to {{ customer_name }} for a principal amount of Rs. {{ principal_amount }} has been fully repaid.

Total amount paid: Rs. {{ total_paid }}
Loan closed on: {{ closing_date }}

{{ company_name }} confirms that the Borrower has no further outstanding dues on this loan account, and this document may be treated as a No Dues Certificate.

Thank you for your association with us.

{{ company_name }}
{{ company_address }}"""


def seed_templates(apps, schema_editor):
    DocumentTemplate = apps.get_model("documents", "DocumentTemplate")
    DocumentType = apps.get_model("documents", "DocumentType")

    DocumentTemplate.objects.get_or_create(category="agreement", defaults={"body": AGREEMENT_DEFAULT})
    DocumentTemplate.objects.get_or_create(category="notice", defaults={"body": NOTICE_DEFAULT})
    DocumentTemplate.objects.get_or_create(category="closing", defaults={"body": CLOSING_DEFAULT})

    # Also seed the three LOAN-scoped DocumentType rows these generated
    # PDFs attach themselves to, with fixed codes the generation views
    # look up by — so this feature works without any manual admin setup.
    DocumentType.objects.get_or_create(
        code="loan_agreement", defaults={"name": "Loan Agreement", "scope": "loan", "display_order": 1}
    )
    DocumentType.objects.get_or_create(
        code="notice_letter", defaults={"name": "Notice Letter", "scope": "loan", "display_order": 2}
    )
    DocumentType.objects.get_or_create(
        code="closing_document", defaults={"name": "Closing Document", "scope": "loan", "display_order": 3}
    )


def unseed_templates(apps, schema_editor):
    DocumentTemplate = apps.get_model("documents", "DocumentTemplate")
    DocumentTemplate.objects.filter(category__in=["agreement", "notice", "closing"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0004_document_template"),
    ]

    operations = [
        migrations.RunPython(seed_templates, unseed_templates),
    ]
