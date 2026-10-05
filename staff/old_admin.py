from django.contrib import admin

from .models import Staff


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "full_name", "mobile", "status", "joining_date")
    search_fields = ("employee_id", "full_name", "mobile", "email")
    list_filter = ("status",)
