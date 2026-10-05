from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import AdminUser


@admin.register(AdminUser)
class AdminUserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Loan Management System settings", {"fields": ("full_name", "session_timeout_minutes")}),
    )
    list_display = ("username", "full_name", "email", "is_staff", "session_timeout_minutes")
