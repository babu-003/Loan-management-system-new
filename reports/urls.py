from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("overdue/", views.overdue_report, name="overdue"),
    path("collections/", views.collection_report, name="collections"),
    path("collections/export/", views.collection_report_csv, name="collections_csv"),
]
