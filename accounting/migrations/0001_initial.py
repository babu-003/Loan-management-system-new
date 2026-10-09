from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


def seed_defaults(apps, schema_editor):
    LedgerAccount = apps.get_model("accounting", "LedgerAccount")
    VoucherCategory = apps.get_model("accounting", "VoucherCategory")
    LedgerAccount.objects.get_or_create(name="Cash", account_type="cash")
    LedgerAccount.objects.get_or_create(name="Bank", account_type="bank")
    for name in ["Salary Expense", "Rent Expense", "Electricity Expense", "Travel Expense", "Stationery Expense", "Other Expense"]:
        LedgerAccount.objects.get_or_create(name=name, account_type="expense")
    defaults = [
        ("Salary", "expense"), ("Rent", "expense"), ("Electricity", "expense"),
        ("Travel", "expense"), ("Stationery", "expense"), ("Other Expense", "expense"),
        ("Borrowing", "borrowing"), ("Repayment", "repayment"),
        ("Investment", "investment"), ("Other", "other"),
    ]
    for name, kind in defaults:
        VoucherCategory.objects.get_or_create(name=name, voucher_type=kind)


def remove_defaults(apps, schema_editor):
    VoucherCategory = apps.get_model("accounting", "VoucherCategory")
    LedgerAccount = apps.get_model("accounting", "LedgerAccount")
    VoucherCategory.objects.filter(name__in=["Salary","Rent","Electricity","Travel","Stationery","Other Expense","Borrowing","Repayment","Investment","Other"]).delete()
    LedgerAccount.objects.filter(name__in=["Cash","Bank","Salary Expense","Rent Expense","Electricity Expense","Travel Expense","Stationery Expense","Other Expense"]).delete()


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("customers", "0001_initial"),
        ("investments", "0002_investmentledgerentry_edited_at_and_more"),
    ]
    operations = [
        migrations.CreateModel(
            name="LedgerAccount",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("account_type", models.CharField(choices=[("cash","Cash"),("bank","Bank"),("customer","Customer"),("expense","Expense"),("borrowing","Borrowing"),("investment","Investment"),("other","Other")], max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("customer", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="accounting_ledgers", to="customers.customer")),
                ("investor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="accounting_ledgers", to="investments.investor")),
            ],
            options={"ordering":["account_type","name"]},
        ),
        migrations.CreateModel(
            name="VoucherCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                ("voucher_type", models.CharField(choices=[("expense","Expense"),("borrowing","Borrowing"),("repayment","Repayment"),("investment","Investment"),("other","Other")], max_length=20)),
                ("is_active", models.BooleanField(default=True)),
            ], options={"ordering":["voucher_type","name"]},
        ),
        migrations.CreateModel(
            name="VoucherCounter",
            fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("last_number", models.PositiveIntegerField(default=0))],
        ),
        migrations.CreateModel(
            name="Voucher",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("voucher_number", models.CharField(editable=False, max_length=30, unique=True)),
                ("voucher_type", models.CharField(choices=[("receipt","Receipt"),("payment","Payment"),("expense","Expense"),("borrowing","Borrowing"),("repayment","Repayment"),("investment","Investment"),("journal","Journal"),("adjustment","Adjustment")], max_length=20)),
                ("voucher_date", models.DateField()),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("payment_mode", models.CharField(choices=[("cash","Cash"),("online","Online / Bank")], default="cash", max_length=10)),
                ("transaction_id", models.CharField(blank=True, max_length=100)),
                ("party_name", models.CharField(blank=True, max_length=150)),
                ("narration", models.TextField(blank=True)),
                ("source_type", models.CharField(blank=True, max_length=50)),
                ("source_id", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("category", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="vouchers", to="accounting.vouchercategory")),
            ], options={"ordering":["-voucher_date","-created_at"]},
        ),
        migrations.CreateModel(
            name="VoucherEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("debit", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("credit", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("narration", models.CharField(blank=True, max_length=255)),
                ("ledger_account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="entries", to="accounting.ledgeraccount")),
                ("voucher", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="entries", to="accounting.voucher")),
            ],
        ),
        migrations.AddConstraint(
            model_name="ledgeraccount",
            constraint=models.UniqueConstraint(fields=("account_type","name"), name="unique_ledger_account_name_type"),
        ),
        migrations.RunPython(seed_defaults, remove_defaults),
    ]
