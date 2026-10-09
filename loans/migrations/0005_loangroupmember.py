from django.db import migrations, models
import django.db.models.deletion


def backfill_group_members(apps, schema_editor):
    Loan = apps.get_model("loans", "Loan")
    LoanGroupMember = apps.get_model("loans", "LoanGroupMember")

    for loan in Loan.objects.filter(loan_group__isnull=False).order_by("id"):
        existing = LoanGroupMember.objects.filter(customer_id=loan.customer_id).first()
        if existing:
            if existing.group_id != loan.loan_group_id:
                raise RuntimeError(
                    "Cannot migrate group memberships: customer ID "
                    f"{loan.customer_id} belongs to more than one loan group. "
                    "Resolve the existing group assignments before migrating."
                )
            continue
        LoanGroupMember.objects.create(
            group_id=loan.loan_group_id,
            customer_id=loan.customer_id,
        )


def reverse_group_members(apps, schema_editor):
    # Membership is a new concept; reversing the migration should remove it.
    LoanGroupMember = apps.get_model("loans", "LoanGroupMember")
    LoanGroupMember.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("loans", "0004_loan_penalty_per_day"),
        ("customers", "0002_customer_default_staff"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoanGroupMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                (
                    "customer",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="loan_group_membership",
                        to="customers.customer",
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="members",
                        to="loans.loangroup",
                    ),
                ),
            ],
            options={
                "ordering": ["joined_at", "id"],
            },
        ),
        migrations.RunPython(backfill_group_members, reverse_group_members),
    ]
