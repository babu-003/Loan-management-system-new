from django.urls import path

from . import views

app_name = "settings"

urlpatterns = [
    path("", views.settings_edit, name="edit"),
    path("audit-log/", views.audit_log_list, name="audit_log"),
    path("backups/", views.backup_list, name="backup_list"),
    path("backups/create/", views.backup_create, name="backup_create"),
    path("backups/<int:pk>/download/", views.backup_download, name="backup_download"),
    path("backups/<int:pk>/restore/", views.backup_restore_confirm, name="backup_restore"),
    path("backups/restore-upload/", views.backup_restore_upload, name="backup_restore_upload"),
    path("backups/<int:pk>/delete/", views.backup_delete, name="backup_delete"),
]
