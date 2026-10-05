from django.urls import path

from . import views

app_name = "staff"

urlpatterns = [
    path("", views.staff_list, name="list"),
    path("add/", views.staff_create, name="add"),
    path("<int:pk>/", views.staff_detail, name="detail"),
    path("<int:pk>/edit/", views.staff_edit, name="edit"),
    path("loans/<int:pk>/assign/", views.assign_loan, name="assign_loan"),
]
