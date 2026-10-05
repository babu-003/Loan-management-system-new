from django.contrib import admin

from .models import CustomerDocument, DocumentType


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "scope", "is_active", "display_order")
    list_filter = ("scope", "is_active")
    ordering = ("scope", "display_order")


@admin.register(CustomerDocument)
class CustomerDocumentAdmin(admin.ModelAdmin):
    list_display = ("customer", "document_type", "document_number", "verified_status", "is_archived", "uploaded_date")
    list_filter = ("verified_status", "document_type", "is_archived")
    search_fields = ("customer__customer_id", "customer__full_name", "document_number")


from .models import LoanDocument, Notice, NoticeType  # noqa: E402


@admin.register(NoticeType)
class NoticeTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "display_order")
    ordering = ("display_order",)


@admin.register(LoanDocument)
class LoanDocumentAdmin(admin.ModelAdmin):
    list_display = ("loan", "document_type", "document_number", "verified_status", "uploaded_date")
    list_filter = ("verified_status", "document_type")
    search_fields = ("loan__loan_number", "loan__customer__full_name", "document_number")


@admin.register(Notice)
class NoticeAdmin(admin.ModelAdmin):
    list_display = ("loan", "notice_type", "notice_date", "reason")
    list_filter = ("notice_type",)
    search_fields = ("loan__loan_number", "loan__customer__full_name", "reason")
