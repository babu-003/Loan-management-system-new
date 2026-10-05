import datetime
import threading
from decimal import Decimal

from django.db.models.signals import post_delete, post_save, pre_save

_local = threading.local()

# Fields never worth diffing — either noisy (auto-managed timestamps) or
# sensitive (password hashes should never land in a readable log).
EXCLUDED_FIELDS = {"created_at", "updated_at", "last_login", "password"}


def set_current_user(user):
    _local.user = user


def get_current_user():
    return getattr(_local, "user", None)


def _serialize(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _snapshot_raw(instance):
    """Raw (unserialized) field values, used for equality comparison —
    comparing Decimal/date objects directly avoids false positives like
    Decimal('12000') vs Decimal('12000.00') looking different as strings
    even though they're numerically equal."""
    return {
        field.name: getattr(instance, field.attname, None)
        for field in instance._meta.fields
        if field.name not in EXCLUDED_FIELDS
    }


def _actor():
    user = get_current_user()
    return user if user and user.is_authenticated else None


def _capture_pre_save(sender, instance, **kwargs):
    """Stashes what the row looked like in the DB BEFORE this save, so
    post_save can diff against it. If this is a brand-new row, there's
    nothing to diff against — that's handled as a 'created' entry."""
    if instance.pk:
        try:
            instance._audit_old_snapshot = _snapshot_raw(sender.objects.get(pk=instance.pk))
        except sender.DoesNotExist:
            instance._audit_old_snapshot = None
    else:
        instance._audit_old_snapshot = None


def _log_post_save(sender, instance, created, **kwargs):
    from .models import AuditLog  # imported here, not at module load, to
    # avoid a circular import between core and the apps it tracks.

    if created:
        AuditLog.objects.create(
            actor=_actor(), action=AuditLog.ACTION_CREATED,
            entity_type=sender.__name__, entity_id=str(instance.pk),
            entity_label=str(instance)[:255],
            changes={k: _serialize(v) for k, v in _snapshot_raw(instance).items()},
        )
        return

    old_snapshot = getattr(instance, "_audit_old_snapshot", None)
    if old_snapshot is None:
        return  # couldn't determine what changed — skip rather than guess

    new_snapshot = _snapshot_raw(instance)
    changed = {
        field: [_serialize(old_snapshot.get(field)), _serialize(new_value)]
        for field, new_value in new_snapshot.items()
        if old_snapshot.get(field) != new_value
    }
    if not changed:
        return  # save() ran but nothing actually differs — no-op, don't log

    AuditLog.objects.create(
        actor=_actor(), action=AuditLog.ACTION_UPDATED,
        entity_type=sender.__name__, entity_id=str(instance.pk),
        entity_label=str(instance)[:255], changes=changed,
    )


def _log_post_delete(sender, instance, **kwargs):
    from .models import AuditLog

    AuditLog.objects.create(
        actor=_actor(), action=AuditLog.ACTION_DELETED,
        entity_type=sender.__name__, entity_id=str(instance.pk),
        entity_label=str(instance)[:255], changes={},
    )


def register():
    """Connects the signals above to the models worth auditing. Called
    once from CoreConfig.ready() — after every app is loaded, so
    importing customers/loans/payments/documents models here is safe."""
    from customers.models import Customer
    from documents.models import CustomerDocument
    from loans.models import Loan, LoanGroup
    from payments.models import Payment

    tracked_models = [Customer, Loan, LoanGroup, Payment, CustomerDocument]
    for model in tracked_models:
        pre_save.connect(_capture_pre_save, sender=model, weak=False)
        post_save.connect(_log_post_save, sender=model, weak=False)
        post_delete.connect(_log_post_delete, sender=model, weak=False)
