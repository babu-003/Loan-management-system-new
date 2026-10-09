from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_adminuser_recovery_code_hash"),
    ]

    operations = [
        migrations.CreateModel(
            name="MasterRecovery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code_hash", models.CharField(blank=True, max_length=128)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Master Recovery",
                "verbose_name_plural": "Master Recovery",
            },
        ),
    ]
