from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="adminuser",
            name="recovery_code_hash",
            field=models.CharField(blank=True, max_length=128),
        ),
    ]
