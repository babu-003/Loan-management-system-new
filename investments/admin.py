from django.contrib import admin

from .models import InvestmentLedgerEntry, Investor


@admin.register(Investor)
class InvestorAdmin(admin.ModelAdmin):
    list_display = ("investor_id", "full_name", "mobile", "status", "total_deposited")
    search_fields = ("investor_id", "full_name", "mobile")


@admin.register(InvestmentLedgerEntry)
class InvestmentLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "entry_type", "investor", "loan", "payment", "amount", "balance_after")
    list_filter = ("entry_type",)
    readonly_fields = ("balance_after",)
