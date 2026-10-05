from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0001_initial"),
        ("staff", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="default_staff",
            field=models.ForeignKey(
                blank=True,
                help_text="Optional staff member to use as the default when this customer gets a new loan.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="default_customers",
                to="staff.staff",
            ),
        ),
    ]
