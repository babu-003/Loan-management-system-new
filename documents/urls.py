from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("", views.document_list, name="list"),
    path("<int:pk>/edit/", views.document_edit, name="edit"),
    path("<int:pk>/archive-toggle/", views.document_archive_toggle, name="archive_toggle"),
    path("loans/<int:loan_pk>/add/", views.loan_document_add, name="loan_document_add"),
    path(
        "loans/<int:loan_pk>/<int:document_id>/verify/",
        views.loan_document_verify, name="loan_document_verify",
    ),
    path("loans/<int:loan_pk>/notices/add/", views.notice_add, name="notice_add"),
    path("templates/", views.template_list, name="template_list"),
    path("templates/<str:category>/edit/", views.template_edit, name="template_edit"),
    path("loans/<int:loan_pk>/generate/agreement/", views.generate_agreement, name="generate_agreement"),
    path("loans/<int:loan_pk>/generate/closing/", views.generate_closing, name="generate_closing"),
    path(
        "loans/<int:loan_pk>/notices/<int:notice_pk>/generate-pdf/",
        views.generate_notice_pdf, name="generate_notice_pdf",
    ),
]
