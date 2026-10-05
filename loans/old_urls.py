from django.urls import path

from . import views

app_name = "loans"

urlpatterns = [
    path("", views.loan_list, name="list"),
    path("add/", views.loan_create, name="add"),
    path("<int:pk>/", views.loan_detail, name="detail"),
    path("<int:pk>/installments/<int:installment_id>/edit-due-date/", views.installment_edit_due_date, name="edit_installment_due_date"),
    path("groups/", views.loan_group_list, name="group_list"),
    path("groups/add/", views.loan_group_create, name="group_add"),
    path("groups/<int:pk>/", views.loan_group_detail, name="group_detail"),
]
