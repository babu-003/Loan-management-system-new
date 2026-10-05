from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("", views.payment_list, name="list"),
    path("add/", views.payment_create, name="add"),
    path("<int:pk>/", views.payment_detail, name="detail"),
    path("<int:pk>/edit/", views.payment_edit, name="edit"),
]
