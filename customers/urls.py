from django.urls import path

from . import views

app_name = "customers"

urlpatterns = [
    path("", views.customer_list, name="list"),
    path("add/", views.CustomerWizard.as_view(), name="add"),
    path("<int:pk>/", views.CustomerDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.CustomerUpdateView.as_view(), name="edit"),
    path("<int:pk>/documents/add/", views.add_customer_document, name="add_document"),
    path(
        "<int:pk>/documents/<int:document_id>/verify/",
        views.verify_customer_document,
        name="verify_document",
    ),
]
