from django.contrib import admin

from .models import Customer, CustomerBankDetail, CustomerReference


class CustomerReferenceInline(admin.TabularInline):
    model = CustomerReference
    extra = 0


class CustomerBankDetailInline(admin.StackedInline):
    model = CustomerBankDetail
    extra = 0
    max_num = 1


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("customer_id", "full_name", "mobile", "permanent_city", "status", "created_at")
    search_fields = ("customer_id", "full_name", "mobile")
    list_filter = ("status", "gender", "marital_status")
    readonly_fields = ("customer_id", "created_at", "updated_at")
    inlines = [CustomerReferenceInline, CustomerBankDetailInline]
