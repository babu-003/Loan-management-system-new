from django.contrib import admin

from .models import InterestType, Installment, Loan, LoanGroup, LoanType


class InstallmentInline(admin.TabularInline):
    model = Installment
    extra = 0
    readonly_fields = ("installment_number", "original_due_date")


@admin.register(LoanType)
class LoanTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")


@admin.register(InterestType)
class InterestTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "calculation_method", "is_active")


@admin.register(LoanGroup)
class LoanGroupAdmin(admin.ModelAdmin):
    list_display = ("group_id", "group_name", "status", "created_at")
    readonly_fields = ("group_id",)


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ("loan_number", "customer", "loan_group", "principal_amount", "total_payable", "status")
    list_filter = ("status", "loan_type", "repayment_frequency")
    search_fields = ("loan_number", "customer__full_name", "customer__customer_id")
    readonly_fields = ("loan_number", "total_interest", "total_payable")
    inlines = [InstallmentInline]
