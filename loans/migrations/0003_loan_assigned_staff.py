from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("loans", "0002_installment_interest_component_and_more"),
        ("staff", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="loan",
            name="assigned_staff",
            field=models.ForeignKey(
                blank=True,
                help_text="Staff member responsible for collecting this loan.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="loans",
                to="staff.staff",
            ),
        ),
    ]
