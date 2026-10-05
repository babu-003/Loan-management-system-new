from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Staff",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("employee_id", models.CharField(max_length=30, unique=True)),
                ("full_name", models.CharField(max_length=150)),
                ("mobile", models.CharField(max_length=10, validators=[django.core.validators.RegexValidator(message="Enter a valid 10-digit mobile number.", regex="^[6-9]\\d{9}$")])),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("joining_date", models.DateField(blank=True, null=True)),
                ("address", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("active", "Active"), ("inactive", "Inactive")], default="active", max_length=10)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["full_name"]},
        ),
    ]
