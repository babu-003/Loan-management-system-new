from django.contrib.auth.models import AbstractUser
from django.db import models


class AdminUser(AbstractUser):
    """Extends Django's built-in User so all the existing password
    hashing, session, and permission machinery keeps working unchanged —
    only two fields added on top, matching the original design doc's
    accounts.AdminUser: full_name and a per-admin session timeout."""

    full_name = models.CharField(max_length=150, blank=True)
    session_timeout_minutes = models.PositiveIntegerField(
        default=30,
        help_text="Auto-logout after this many minutes of inactivity.",
    )

    def __str__(self):
        return self.full_name or self.username
