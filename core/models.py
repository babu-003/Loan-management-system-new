from django.conf import settings
from django.db import models

# Known setting keys and their defaults. New settings can be added here
# later without any migration — SystemSetting is a plain key/value table,
# so a new key is just a new row, not a new column.
DEFAULTS = {
    "company_name": "",
    "company_address": "",
    "company_phone": "",
    "company_email": "",
    "currency_symbol": "₹",
    "date_format": "%d-%m-%Y",
    "customer_id_prefix": "CUS",
    "loan_id_prefix": "LN",
    "group_id_prefix": "GRP",
    "receipt_id_prefix": "REC",
    "id_number_padding": "6",
}


class SystemSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True)

    def __str__(self):
        return self.key


class AuditLog(models.Model):
    """Append-only record of who changed what, when. Populated
    automatically by signals (see signals.py) for Customer, Loan,
    LoanGroup, Payment, and CustomerDocument — nothing writes here
    directly, and nothing should ever edit or delete a row once made."""

    ACTION_CREATED = "created"
    ACTION_UPDATED = "updated"
    ACTION_DELETED = "deleted"
    ACTION_CHOICES = [
        (ACTION_CREATED, "Created"),
        (ACTION_UPDATED, "Updated"),
        (ACTION_DELETED, "Deleted"),
    ]

    timestamp = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=50)
    entity_label = models.CharField(max_length=255, blank=True)
    changes = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.get_action_display()} {self.entity_type} #{self.entity_id}"


class BackupRecord(models.Model):
    """One entry per backup zip taken. The file itself lives under
    BASE_DIR/backups/ — a plain directory, not served as static/media,
    so it's only reachable through the login-gated download view."""

    filename = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    size_bytes = models.PositiveIntegerField(default=0)
    notes = models.CharField(max_length=255, blank=True)
    restored_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.filename

    @property
    def size_display(self):
        size = float(self.size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


def get_setting(key, default=None):
    """Reads a setting, falling back to DEFAULTS (then the given default)
    if it's never been saved yet — so the app works with zero setup and
    only writes a row once an admin actually changes something."""
    try:
        return SystemSetting.objects.get(key=key).value
    except SystemSetting.DoesNotExist:
        return DEFAULTS.get(key, default)


def set_setting(key, value):
    SystemSetting.objects.update_or_create(key=key, defaults={"value": value})
