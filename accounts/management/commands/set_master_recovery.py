from getpass import getpass

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError

from accounts.models import MasterRecovery


class Command(BaseCommand):
    help = "Set or replace the application master recovery code. The code is stored only as a hash."

    def handle(self, *args, **options):
        code = getpass("Enter new master recovery code (minimum 8 characters): ").strip()
        if len(code) < 8:
            raise CommandError("Master recovery code must contain at least 8 characters.")

        confirm = getpass("Confirm master recovery code: ").strip()
        if code != confirm:
            raise CommandError("The master recovery codes do not match.")

        MasterRecovery.objects.update_or_create(
            pk=1,
            defaults={"code_hash": make_password(code)},
        )
        self.stdout.write(self.style.SUCCESS("Master recovery code saved securely as a hash."))
        self.stdout.write("Keep the actual code outside the application in a secure place.")
