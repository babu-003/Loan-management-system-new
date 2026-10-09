from django.contrib import admin

from .models import (
    LedgerAccount,
    Voucher,
    VoucherCategory,
    VoucherEntry,
)


admin.site.register(LedgerAccount)

admin.site.register(VoucherCategory)


class VoucherEntryInline(admin.TabularInline):

    model = VoucherEntry

    extra = 0

    readonly_fields = (
        "debit",
        "credit",
    )


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):

    list_display = (
        "voucher_number",
        "voucher_date",
        "voucher_type",
        "amount",
        "payment_mode",
        "party_name",
    )

    list_filter = (
        "voucher_type",
        "payment_mode",
        "voucher_date",
    )

    search_fields = (
        "voucher_number",
        "party_name",
        "transaction_id",
        "narration",
    )

    inlines = [
        VoucherEntryInline
    ]