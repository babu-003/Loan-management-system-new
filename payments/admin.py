from django.contrib import admin

from .models import Payment, PaymentAllocation


class PaymentAllocationInline(admin.TabularInline):
    model = PaymentAllocation
    extra = 0
    readonly_fields = ("installment", "amount_allocated")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "loan", "payment_date", "amount_paid", "previous_amount", "unallocated_amount")
    search_fields = ("receipt_number", "loan__loan_number", "loan__customer__full_name")
    readonly_fields = ("receipt_number", "previous_amount", "edited_at", "unallocated_amount")
    inlines = [PaymentAllocationInline]
