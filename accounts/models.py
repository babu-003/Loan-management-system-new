from django.contrib.auth.models import AbstractUser
from django.db import models


class AdminUser(AbstractUser):
    """Application administrator account."""

    full_name = models.CharField(max_length=150, blank=True)
    session_timeout_minutes = models.PositiveIntegerField(
        default=30,
        help_text="Auto-logout after this many minutes of inactivity.",
    )
    # Stored as a hash, never as the actual recovery code.
    recovery_code_hash = models.CharField(max_length=128, blank=True)

    def __str__(self):
        return self.full_name or self.username
