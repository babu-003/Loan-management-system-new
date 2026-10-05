from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AuditLogFilterForm, SystemSettingsForm
from .models import AuditLog, DEFAULTS, get_setting, set_setting


@login_required
def settings_edit(request):
    if request.method == "POST":
        form = SystemSettingsForm(request.POST)
        if form.is_valid():
            for key in DEFAULTS:
                set_setting(key, str(form.cleaned_data[key]))
            messages.success(request, "Settings updated.")
            return redirect("settings:edit")
    else:
        initial = {key: get_setting(key) for key in DEFAULTS}
        form = SystemSettingsForm(initial=initial)
    return render(request, "core/settings_form.html", {"form": form})


@login_required
def audit_log_list(request):
    form = AuditLogFilterForm(request.GET or None)
    logs = AuditLog.objects.select_related("actor")

    if form.is_valid():
        q = form.cleaned_data.get("q")
        entity_type = form.cleaned_data.get("entity_type")
        action = form.cleaned_data.get("action")
        date_from = form.cleaned_data.get("date_from")
        date_to = form.cleaned_data.get("date_to")
        if q:
            logs = logs.filter(entity_label__icontains=q)
        if entity_type:
            logs = logs.filter(entity_type=entity_type)
        if action:
            logs = logs.filter(action=action)
        if date_from:
            logs = logs.filter(timestamp__date__gte=date_from)
        if date_to:
            logs = logs.filter(timestamp__date__lte=date_to)

    paginator = Paginator(logs, 30)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "core/audit_log_list.html", {"page_obj": page_obj, "form": form})


from django.http import FileResponse, Http404  # noqa: E402
from django.utils import timezone  # noqa: E402

from . import backup as backup_utils  # noqa: E402
from .models import BackupRecord  # noqa: E402


@login_required
def backup_list(request):
    records = list(BackupRecord.objects.all())
    for record in records:
        record.file_exists = (backup_utils.BACKUP_DIR / record.filename).exists()
    return render(request, "core/backup_list.html", {"records": records})


@login_required
def backup_create(request):
    if request.method == "POST":
        record = backup_utils.create_backup()
        messages.success(request, f"Backup created: {record.filename} ({record.size_display}).")
    return redirect("settings:backup_list")


@login_required
def backup_download(request, pk):
    record = get_object_or_404(BackupRecord, pk=pk)
    filepath = backup_utils.BACKUP_DIR / record.filename
    if not filepath.exists():
        raise Http404("Backup file not found on disk.")
    return FileResponse(open(filepath, "rb"), as_attachment=True, filename=record.filename)


@login_required
def backup_restore_confirm(request, pk):
    record = get_object_or_404(BackupRecord, pk=pk)
    filepath = backup_utils.BACKUP_DIR / record.filename
    if request.method == "POST":
        if not filepath.exists():
            messages.error(request, "Backup file not found on disk — cannot restore.")
            return redirect("settings:backup_list")
        backup_utils.restore_backup(filepath)
        record.restored_at = timezone.now()
        record.save(update_fields=["restored_at"])
        messages.success(
            request,
            "Restore complete. A safety backup of the previous state was taken automatically. "
            "Please restart the server for the changes to fully take effect.",
        )
        return redirect("settings:backup_list")
    return render(request, "core/backup_restore_confirm.html", {"record": record})


@login_required
def backup_restore_upload(request):
    if request.method == "POST":
        uploaded = request.FILES.get("backup_file")
        if not uploaded:
            messages.error(request, "Choose a backup file to upload.")
        elif not backup_utils.validate_backup_zip(uploaded):
            messages.error(request, "That file doesn't look like a valid backup (no db.sqlite3 found inside it).")
        else:
            uploaded.seek(0)
            backup_utils.restore_backup(uploaded)
            BackupRecord.objects.create(
                filename=uploaded.name, size_bytes=uploaded.size,
                notes="Restored from an uploaded file", restored_at=timezone.now(),
            )
            messages.success(
                request,
                "Restore complete. A safety backup of the previous state was taken automatically. "
                "Please restart the server for the changes to fully take effect.",
            )
            return redirect("settings:backup_list")
    return render(request, "core/backup_restore_upload.html")


@login_required
def backup_delete(request, pk):
    record = get_object_or_404(BackupRecord, pk=pk)
    if request.method == "POST":
        filepath = backup_utils.BACKUP_DIR / record.filename
        if filepath.exists():
            filepath.unlink()
        record.delete()
        messages.success(request, "Backup deleted.")
    return redirect("settings:backup_list")
