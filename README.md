# Customer Management Module

Implements the **Customer Management** module only, on top of the database
design agreed earlier: `customers` app (Customer, CustomerReference,
CustomerBankDetail) + the customer-facing part of the `documents` app
(DocumentType, CustomerDocument). No loan/payment/audit models were touched.

## Run it locally

```
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser      # creates your admin login
python manage.py runserver
```

Open http://127.0.0.1:8000 — it redirects to the customer list, which
requires login.

Seed a few document types before adding your first customer (Settings
module will do this through the UI later — for now, use /admin/):

```
python manage.py shell
>>> from documents.models import DocumentType
>>> DocumentType.objects.create(name="Aadhaar", code="aadhaar", scope="customer")
>>> DocumentType.objects.create(name="PAN", code="pan", scope="customer")
```

## What's implemented

- **Add Customer** — 5-step wizard (Personal → Address → Reference →
  Bank → Documents), nothing saved until the last step, all in one
  database transaction.
- **Customer List** — search by ID / name / mobile / loan number,
  status filter, location filter, date-range filter, pagination.
- **Customer Profile** — tabs: Overview, Personal, Address, Reference,
  Bank, Documents.
- **Edit Customer** — single combined form (no wizard needed for edits).
- **Documents** — add a document after creation, mark
  Pending/Verified/Rejected from the profile page.

## Deliberate design decisions (please review)

1. **Document proof is file OR ID number, not just file.** Every
   document row lets you upload a file, or type the document/ID number,
   or both — but not neither. This is enforced in the form and again in
   `CustomerDocument.clean()`, so it holds even if a document is added
   later outside the wizard.

2. **"Individual vs. Group" at customer creation is informational
   only.** Per the design we agreed earlier, group membership belongs to
   `Loan`/`LoanGroup`, not `Customer` — a customer must stay a fully
   independent record whether they end up in an individual loan or a
   group loan. So Step 1 has a "Customer category" choice, but it is
   **not saved anywhere** — it only changes the confirmation message
   after saving, pointing you to the right next step. If you actually
   want this stored on the customer record, say so and I'll adjust the
   design (it would be a deliberate change from the earlier agreed
   schema, not a bug).

3. **Almost every field is required**, per your instruction — the only
   optional fields are alternate mobile, email, and photo (a person can
   legitimately not have those). Everything else, including all of
   Personal, Address, Reference, and Bank Details, is compulsory.

4. **Login uses Django's built-in auth for now**, not a custom
   `AdminUser` model — the full admin-login/session-timeout module
   (spec §5) is its own `accounts` app and wasn't in scope for "customer
   management module only." Swapping it in later won't touch anything
   in `customers` or `documents`.

5. **No CDN dependencies** — one local stylesheet at
   `static/css/app.css`, per the offline requirement.

## Not included (out of scope for this module)

Loan, LoanGroup, Installment, Payment, LoanDocument, Notice, AuditLog,
SystemSetting, and the real AdminUser/session-timeout system — these
come with their own modules later.
