import importlib

from django.db import migrations, models

from documents.i18n import DEFAULT_TEMPLATES


def add_tamil_and_update_defaults(apps, schema_editor):
    """Fill in the Tamil text for each template, and swap the English
    text over to the new wording (no total-payable figure, no interest
    in the notice) — but only where the English text is still exactly
    what migration 0005 seeded. A template an admin has already edited
    is left alone."""
    DocumentTemplate = apps.get_model("documents", "DocumentTemplate")
    seed = importlib.import_module("documents.migrations.0005_seed_document_templates")
    old_defaults = {
        "agreement": seed.AGREEMENT_DEFAULT,
        "notice": seed.NOTICE_DEFAULT,
        "closing": seed.CLOSING_DEFAULT,
    }
    for category, texts in DEFAULT_TEMPLATES.items():
        template, _ = DocumentTemplate.objects.get_or_create(
            category=category, defaults={"body": texts["en"], "body_ta": texts["ta"]},
        )
        changed = []
        if not template.body_ta:
            template.body_ta = texts["ta"]
            changed.append("body_ta")
        if template.body.strip() == old_defaults[category].strip():
            template.body = texts["en"]
            changed.append("body")
        if changed:
            template.save(update_fields=changed)


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0005_seed_document_templates"),
    ]

    operations = [
        migrations.AddField(
            model_name="documenttemplate",
            name="body_ta",
            field=models.TextField(blank=True, default="", verbose_name="Tamil text (தமிழ்)"),
        ),
        migrations.AlterField(
            model_name="documenttemplate",
            name="body",
            field=models.TextField(verbose_name="English text"),
        ),
        migrations.RunPython(add_tamil_and_update_defaults, migrations.RunPython.noop),
    ]
