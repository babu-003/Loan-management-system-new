"""English / Tamil wording for the three generated documents (Loan
Agreement, Notice, Closing Document).

Kept free of Django imports so migrations, models, views and the PDF
generator can all import it safely."""

LANGUAGES = [("ta", "தமிழ் (Tamil)"), ("en", "English")]
DEFAULT_LANGUAGE = "ta"
LANGUAGE_CODES = [code for code, _ in LANGUAGES]

STRINGS = {
    "en": {
        "phone_prefix": "Ph:",
        "rs": "Rs.",
        "per_annum": "{rate}% p.a.",
        "loan_no": "Loan No.",
        "customer_name": "Customer Name",
        "principal_amount": "Principal Amount",
        "interest_rate": "Interest Rate",
        "installments": "Number of Installments",
        "frequency": "Repayment Frequency",
        "start_date": "Start Date",
        "overdue_installments": "Overdue Installments",
        "notice_date": "Notice Date",
        "principal_returned": "Principal Amount Returned",
        "closing_date": "Closing Date",
        "title_agreement": "Loan Agreement",
        "title_closing": "Loan Closing Document",
        "title_notice_fallback": "Notice",
        "signatory": "Authorized Signatory",
        "borrower_signature": "Borrower's Signature",
    },
    "ta": {
        "phone_prefix": "தொலைபேசி:",
        "rs": "ரூ.",
        "per_annum": "ஆண்டுக்கு {rate}%",
        "loan_no": "கடன் எண்",
        "customer_name": "வாடிக்கையாளர் பெயர்",
        "principal_amount": "அசல் தொகை",
        "interest_rate": "வட்டி விகிதம்",
        "installments": "தவணைகளின் எண்ணிக்கை",
        "frequency": "திருப்பிச் செலுத்தும் முறை",
        "start_date": "தொடக்க தேதி",
        "overdue_installments": "நிலுவையிலுள்ள தவணைகள்",
        "notice_date": "அறிவிப்பு தேதி",
        "principal_returned": "திருப்பிச் செலுத்தப்பட்ட அசல் தொகை",
        "closing_date": "கடன் முடிவு தேதி",
        "title_agreement": "கடன் ஒப்பந்தம்",
        "title_closing": "கடன் முடிவு ஆவணம்",
        "title_notice_fallback": "அறிவிப்பு",
        "signatory": "அங்கீகரிக்கப்பட்ட கையொப்பதாரர்",
        "borrower_signature": "கடன் பெற்றவரின் கையொப்பம்",
    },
}

# Tamil for the values that come out of the database in English. Matched
# case-insensitively; anything not listed is shown exactly as stored.
FREQUENCY_TA = {
    "daily": "தினசரி",
    "weekly": "வாராந்திர",
    "fortnightly": "இருவார",
    "monthly": "மாதாந்திர",
    "quarterly": "காலாண்டு",
    "half-yearly": "அரையாண்டு",
    "yearly": "ஆண்டு",
}
NOTICE_TITLE_TA = {
    "first notice": "முதல் அறிவிப்பு",
    "second notice": "இரண்டாம் அறிவிப்பு",
    "third notice": "மூன்றாம் அறிவிப்பு",
    "final notice": "இறுதி அறிவிப்பு",
}


def tr(lang, key):
    return STRINGS.get(lang, STRINGS["en"])[key]


def frequency_label(lang, display_value):
    if lang == "ta":
        return FREQUENCY_TA.get(str(display_value).strip().lower(), display_value)
    return display_value


def notice_title(lang, notice_type_name):
    if lang == "ta":
        return NOTICE_TITLE_TA.get(
            str(notice_type_name).strip().lower(), tr("ta", "title_notice_fallback")
        )
    return notice_type_name


# ---------------------------------------------------------------------------
# Default wording. No interest in the notice, and no "total payable /
# total paid" figure in any of the three documents.
# ---------------------------------------------------------------------------

AGREEMENT_EN = """This Loan Agreement is made on {{ today_date }} between {{ company_name }}, having its office at {{ company_address }} (hereinafter referred to as the "Lender"), and {{ customer_name }}, residing at {{ customer_address }}, mobile number {{ customer_mobile }} (hereinafter referred to as the "Borrower").

The Lender agrees to lend, and the Borrower agrees to borrow, a sum of Rs. {{ principal_amount }} (Loan No. {{ loan_number }}) at an interest rate of {{ interest_rate }}% per annum, calculated on a {{ interest_type }} basis.

The loan shall be repaid in {{ number_of_installments }} {{ repayment_frequency }} installments, commencing from {{ first_due_date }}.

The Borrower agrees to repay each installment on or before its due date. Failure to pay any installment may result in the Lender issuing a formal notice and taking appropriate recovery action as per applicable law.

Both parties have read and understood the terms of this agreement and agree to be bound by them."""

AGREEMENT_TA = """இந்தக் கடன் ஒப்பந்தம் {{ today_date }} அன்று, {{ company_address }} என்ற முகவரியில் அலுவலகம் கொண்ட {{ company_name }} (இனி "கடன் வழங்குபவர்" என்று குறிப்பிடப்படுவார்) மற்றும் {{ customer_address }} என்ற முகவரியில் வசிக்கும், கைபேசி எண் {{ customer_mobile }} கொண்ட {{ customer_name }} (இனி "கடன் பெறுபவர்" என்று குறிப்பிடப்படுவார்) ஆகியோருக்கு இடையே செய்யப்படுகிறது.

கடன் வழங்குபவர் ரூ. {{ principal_amount }} (கடன் எண் {{ loan_number }}) தொகையை ஆண்டுக்கு {{ interest_rate }}% வட்டி விகிதத்தில், {{ interest_type }} முறையில் கணக்கிட்டு கடனாக வழங்கவும், கடன் பெறுபவர் அதனைப் பெற்றுக்கொள்ளவும் ஒப்புக்கொள்கின்றனர்.

இக்கடன் {{ first_due_date }} முதல் தொடங்கி, {{ number_of_installments }} {{ repayment_frequency }} தவணைகளில் திருப்பிச் செலுத்தப்படவேண்டும்.

கடன் பெறுபவர் ஒவ்வொரு தவணையையும் அதற்குரிய நிலுவை தேதிக்குள் அல்லது அதற்கு முன் செலுத்த ஒப்புக்கொள்கிறார். ஏதேனும் தவணையைச் செலுத்தத் தவறினால், கடன் வழங்குபவர் முறையான அறிவிப்பை அனுப்பவும், பொருந்தக்கூடிய சட்டத்தின்படி உரிய வசூல் நடவடிக்கை எடுக்கவும் உரிமை உண்டு.

இரு தரப்பினரும் இவ்வொப்பந்தத்தின் நிபந்தனைகளைப் படித்துப் புரிந்துகொண்டு, அவற்றிற்குக் கட்டுப்படுவதாக ஒப்புக்கொள்கின்றனர்."""

NOTICE_EN = """To,
{{ customer_name }}
{{ customer_address }}

Subject: {{ notice_type }} regarding Loan No. {{ loan_number }}

Dear {{ customer_name }},

This is to bring to your attention that {{ company_name }} has given you a loan of Rs. {{ principal_amount }} (Loan No. {{ loan_number }}), and {{ overdue_count }} installment(s) on this loan are currently overdue.

Reason: {{ notice_reason }}

You are hereby requested to return the principal amount of Rs. {{ principal_amount }} at the earliest to avoid further action. Please contact us at {{ company_phone }} or visit our office at {{ company_address }} to settle the dues or discuss a repayment plan.

Failure to respond to this notice may result in further recovery action as per the terms of your loan agreement.

Regards,
{{ company_name }}"""

NOTICE_TA = """பெறுநர்,
{{ customer_name }}
{{ customer_address }}

பொருள்: கடன் எண் {{ loan_number }} தொடர்பான {{ notice_type }}

அன்புடையீர் {{ customer_name }},

{{ company_name }} நிறுவனம் உங்களுக்கு ரூ. {{ principal_amount }} கடனாக வழங்கியுள்ளது (கடன் எண் {{ loan_number }}). இக்கடனில் {{ overdue_count }} தவணை(கள்) தற்போது நிலுவையில் உள்ளன என்பதை உங்கள் கவனத்திற்குக் கொண்டுவருகிறோம்.

காரணம்: {{ notice_reason }}

மேலும் நடவடிக்கை எடுக்கப்படுவதைத் தவிர்க்க, அசல் தொகையான ரூ. {{ principal_amount }}-ஐ விரைவில் திருப்பிச் செலுத்துமாறு கேட்டுக்கொள்கிறோம். நிலுவையைச் செலுத்த அல்லது திருப்பிச் செலுத்தும் திட்டம் குறித்துப் பேச, {{ company_phone }} என்ற எண்ணில் எங்களைத் தொடர்புகொள்ளவும் அல்லது {{ company_address }} என்ற முகவரியிலுள்ள எங்கள் அலுவலகத்திற்கு வரவும்.

இந்த அறிவிப்புக்குப் பதிலளிக்கத் தவறினால், உங்கள் கடன் ஒப்பந்த நிபந்தனைகளின்படி மேலும் வசூல் நடவடிக்கை எடுக்கப்படலாம்.

இங்ஙனம்,
{{ company_name }}"""

CLOSING_EN = """This is to certify that the loan bearing Loan No. {{ loan_number }} issued to {{ customer_name }} for a principal amount of Rs. {{ principal_amount }} has been fully repaid.

Principal amount returned: Rs. {{ principal_amount }}
Loan closed on: {{ closing_date }}

{{ company_name }} confirms that the Borrower has no further outstanding dues on this loan account, and this document may be treated as a No Dues Certificate.

Thank you for your association with us.

{{ company_name }}
{{ company_address }}"""

CLOSING_TA = """{{ customer_name }} அவர்களுக்கு வழங்கப்பட்ட, கடன் எண் {{ loan_number }} கொண்ட, அசல் தொகை ரூ. {{ principal_amount }} கடன் முழுமையாகத் திருப்பிச் செலுத்தப்பட்டுவிட்டது என்று இதன்மூலம் சான்றளிக்கப்படுகிறது.

திருப்பிச் செலுத்தப்பட்ட அசல் தொகை: ரூ. {{ principal_amount }}
கடன் முடிக்கப்பட்ட தேதி: {{ closing_date }}

இக்கடன் கணக்கில் கடன் பெற்றவருக்கு மேலும் எவ்வித நிலுவையும் இல்லை என்பதை {{ company_name }} உறுதிப்படுத்துகிறது; இந்த ஆவணத்தை நிலுவையில்லாச் சான்றிதழாகக் கருதலாம்.

எங்களுடன் தொடர்பில் இருந்தமைக்கு நன்றி.

{{ company_name }}
{{ company_address }}"""

DEFAULT_TEMPLATES = {
    "agreement": {"en": AGREEMENT_EN, "ta": AGREEMENT_TA},
    "notice": {"en": NOTICE_EN, "ta": NOTICE_TA},
    "closing": {"en": CLOSING_EN, "ta": CLOSING_TA},
}


def default_body(category, lang):
    return DEFAULT_TEMPLATES.get(category, {}).get(lang, "")
