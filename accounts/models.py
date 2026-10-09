from django.contrib.auth.hashers import check_password
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


class MasterRecovery(models.Model):
    """Application-wide master recovery credential.

    Only a hash is stored. The actual master recovery code must be kept
    separately by the application owner/developer.
    """

    code_hash = models.CharField(max_length=128, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Master Recovery"
        verbose_name_plural = "Master Recovery"

    def __str__(self):
        return "Master Recovery"

    def check_code(self, code):
        return bool(self.code_hash and check_password(code, self.code_hash))
