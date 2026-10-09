from django.urls import path

from . import views

app_name = "loans"

urlpatterns = [
    path("", views.loan_list, name="list"),
    path("calculator/", views.loan_calculator, name="calculator"),
    path("add/", views.loan_create, name="add"),
    path("<int:pk>/", views.loan_detail, name="detail"),
    path("<int:pk>/repayment-card.pdf", views.repayment_card_pdf, name="repayment_card_pdf"),
    path("<int:pk>/delete/", views.loan_delete, name="delete"),
    path("<int:pk>/installments/<int:installment_id>/edit-due-date/", views.installment_edit_due_date, name="edit_installment_due_date"),
    path("groups/", views.loan_group_list, name="group_list"),
    path("groups/add/", views.loan_group_create, name="group_add"),
    path("groups/<int:pk>/", views.loan_group_detail, name="group_detail"),
    path(
    "create/",
    views.loan_create,
    name="create",
),
path(
    "groups/<int:group_pk>/add-loan/",
    views.loan_create,
    name="group_add_loan",
),
    path(
    "groups/<int:pk>/members/add/",
    views.loan_group_add_member,
    name="group_add_member",
),

]
