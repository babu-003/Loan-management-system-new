from django.db import migrations, models
import django.db.models.deletion


def seed_strict_categories(apps, schema_editor):
    LedgerAccount = apps.get_model("accounting", "LedgerAccount")
    VoucherCategory = apps.get_model("accounting", "VoucherCategory")

    # Existing expense categories map to their specific expense ledgers.
    expense_map = {
        "Salary": "Salary Expense",
        "Rent": "Rent Expense",
        "Electricity": "Electricity Expense",
        "Travel": "Travel Expense",
        "Stationery": "Stationery Expense",
        "Other Expense": "Other Expense",
    }
    for category_name, ledger_name in expense_map.items():
        category = VoucherCategory.objects.filter(name=category_name, voucher_type="expense").first()
        if category:
            ledger = LedgerAccount.objects.get_or_create(name=ledger_name, account_type="expense")[0]
            category.ledger_account_id = ledger.pk
            category.save(update_fields=["ledger_account"])

    for name in ["Stocks", "Mutual Funds", "Fixed Deposit", "Other Investment"]:
        ledger = LedgerAccount.objects.get_or_create(name=name, account_type="investment")[0]
        category, _ = VoucherCategory.objects.get_or_create(name=name, defaults={"voucher_type": "investment", "is_active": True})
        if category.voucher_type != "investment":
            category.voucher_type = "investment"
        category.ledger_account_id = ledger.pk
        category.is_active = True
        category.save(update_fields=["voucher_type", "ledger_account", "is_active"])

    for name in ["Interest Income", "Service Income", "Other Income"]:
        ledger = LedgerAccount.objects.get_or_create(name=name, account_type="income")[0]
        category, _ = VoucherCategory.objects.get_or_create(name=name, defaults={"voucher_type": "income", "is_active": True})
        if category.voucher_type != "income":
            category.voucher_type = "income"
        category.ledger_account_id = ledger.pk
        category.is_active = True
        category.save(update_fields=["voucher_type", "ledger_account", "is_active"])


def reverse_strict_categories(apps, schema_editor):
    VoucherCategory = apps.get_model("accounting", "VoucherCategory")
    LedgerAccount = apps.get_model("accounting", "LedgerAccount")
    VoucherCategory.objects.filter(name__in=["Stocks", "Mutual Funds", "Fixed Deposit", "Other Investment", "Interest Income", "Service Income", "Other Income"]).delete()
    LedgerAccount.objects.filter(name__in=["Stocks", "Mutual Funds", "Fixed Deposit", "Other Investment", "Interest Income", "Service Income", "Other Income"]).delete()


class Migration(migrations.Migration):
    dependencies = [("accounting", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="ledgeraccount",
            name="account_type",
            field=models.CharField(choices=[("cash", "Cash"), ("bank", "Bank"), ("customer", "Customer"), ("expense", "Expense"), ("borrowing", "Borrowing"), ("investment", "Investment"), ("income", "Income"), ("other", "Other")], max_length=20),
        ),
        migrations.AlterField(
            model_name="vouchercategory",
            name="voucher_type",
            field=models.CharField(choices=[("expense", "Expense"), ("borrowing", "Borrowing"), ("repayment", "Repayment"), ("investment", "Investment"), ("income", "Income"), ("other", "Other")], max_length=20),
        ),
        migrations.AddField(
            model_name="vouchercategory",
            name="ledger_account",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="categories", to="accounting.ledgeraccount"),
        ),
        migrations.AlterField(
            model_name="voucher",
            name="payment_mode",
            field=models.CharField(choices=[("cash", "Cash"), ("online", "Online / Bank"), ("upi", "UPI"), ("cheque", "Cheque")], default="cash", max_length=10),
        ),
        migrations.AlterField(
            model_name="voucher",
            name="voucher_type",
            field=models.CharField(choices=[("receipt", "Receipt"), ("payment", "Payment"), ("expense", "Expense"), ("borrowing", "Borrowing"), ("repayment", "Repayment"), ("investment", "Investment"), ("income", "Income"), ("journal", "Journal"), ("adjustment", "Adjustment")], max_length=20),
        ),
        migrations.RunPython(seed_strict_categories, reverse_strict_categories),
    ]
