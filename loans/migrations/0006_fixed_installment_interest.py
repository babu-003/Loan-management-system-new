from django.db import migrations, models


def add_fixed_interest_type(apps, schema_editor):
    InterestType = apps.get_model("loans", "InterestType")
    existing = InterestType.objects.filter(calculation_method="fixed").first()
    if existing:
        if not existing.is_active:
            existing.is_active = True
            existing.save(update_fields=["is_active"])
        return
    InterestType.objects.create(
        name="Fixed Interest",
        calculation_method="fixed",
        is_active=True,
    )


def remove_fixed_interest_type(apps, schema_editor):
    InterestType = apps.get_model("loans", "InterestType")
    # Do not delete a method that has been used by a loan.
    if not apps.get_model("loans", "Loan").objects.filter(interest_type__calculation_method="fixed").exists():
        InterestType.objects.filter(calculation_method="fixed", name="Fixed Interest").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0005_loangroupmember"),
    ]

    operations = [
        migrations.AlterField(
            model_name="interesttype",
            name="calculation_method",
            field=models.CharField(
                choices=[
                    ("flat", "Flat Interest"),
                    ("reducing", "Reducing Balance"),
                    ("fixed", "Fixed Interest"),
                ],
                default="flat",
                max_length=20,
            ),
        ),
        migrations.RunPython(add_fixed_interest_type, remove_fixed_interest_type),
    ]
