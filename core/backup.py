import zipfile
from pathlib import Path

from django.conf import settings
from django.db import connections
from django.utils import timezone

BACKUP_DIR = Path(settings.BASE_DIR) / "backups"


def _db_path():
    return Path(settings.DATABASES["default"]["NAME"])


def create_backup(notes=""):
    """Zips the current db.sqlite3 + everything under MEDIA_ROOT (customer
    photos, KYC documents) into one timestamped file, and records it.
    The BackupRecord row is created BEFORE the zip is taken (size filled
    in afterward) so the snapshot includes a row for itself — otherwise,
    restoring an earlier backup would erase all backup history, since a
    record created after its own snapshot can't be inside that snapshot.
    Guards against ever overwriting an existing backup file — if two
    backups land in the same second, a numeric suffix is added instead
    of silently colliding."""
    from .models import BackupRecord

    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backup_{timestamp}.zip"
    filepath = BACKUP_DIR / filename
    counter = 1
    while filepath.exists():
        filename = f"backup_{timestamp}_{counter}.zip"
        filepath = BACKUP_DIR / filename
        counter += 1

    record = BackupRecord.objects.create(filename=filename, size_bytes=0, notes=notes)

    connections.close_all()  # don't zip the db file mid-write

    with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as zf:
        db_path = _db_path()
        if db_path.exists():
            zf.write(db_path, arcname="db.sqlite3")
        media_root = Path(settings.MEDIA_ROOT)
        if media_root.exists():
            for file_path in media_root.rglob("*"):
                if file_path.is_file():
                    zf.write(file_path, arcname=str(Path("media") / file_path.relative_to(media_root)))

    record.size_bytes = filepath.stat().st_size
    record.save(update_fields=["size_bytes"])
    return record


def validate_backup_zip(file_obj):
    """True if the file looks like a genuine backup (has db.sqlite3 at
    its root) — checked BEFORE anything live gets touched."""
    try:
        with zipfile.ZipFile(file_obj) as zf:
            return "db.sqlite3" in zf.namelist()
    except zipfile.BadZipFile:
        return False


def restore_backup(file_path_or_obj):
    """Overwrites the live database and media files from a backup zip.
    Always takes an automatic safety snapshot of the CURRENT state first
    — so even a bad restore is recoverable, by restoring that snapshot.

    Reads the ENTIRE source archive into memory before doing anything
    else. This matters: without it, if the source backup and the
    automatic safety snapshot ever land on the same filename (e.g. two
    backups within the same second), taking the safety backup would
    silently overwrite the very file being restored from, destroying it
    before it's read."""
    import io

    if hasattr(file_path_or_obj, "read"):
        file_path_or_obj.seek(0)
        source_bytes = file_path_or_obj.read()
    else:
        with open(file_path_or_obj, "rb") as f:
            source_bytes = f.read()
    source_buffer = io.BytesIO(source_bytes)

    safety_record = create_backup(notes="Automatic safety backup taken before a restore")

    connections.close_all()
    db_path = _db_path()
    media_root = Path(settings.MEDIA_ROOT)
    media_root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(source_buffer) as zf:
        for name in zf.namelist():
            if name == "db.sqlite3":
                with zf.open(name) as source, open(db_path, "wb") as target:
                    target.write(source.read())
            elif name.startswith("media/") and not name.endswith("/"):
                target_path = media_root / name[len("media/"):]
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as source, open(target_path, "wb") as target:
                    target.write(source.read())

    connections.close_all()
    return safety_record
