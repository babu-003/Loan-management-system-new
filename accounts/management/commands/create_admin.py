import os

from django.core.management.base import BaseCommand
from accounts.models import AdminUser


class Command(BaseCommand):
    help = "Create the initial admin user if it does not exist"

    def handle(self, *args, **options):
        username = os.environ.get("ADMIN_USERNAME")
        password = os.environ.get("ADMIN_PASSWORD")

        if not username or not password:
            self.stdout.write(
                self.style.WARNING(
                    "ADMIN_USERNAME or ADMIN_PASSWORD not set. Skipping admin creation."
                )
            )
            return

        if AdminUser.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(
                    f"Admin user '{username}' already exists."
                )
            )
            return

        user = AdminUser.objects.create_superuser(
            username=username,
            password=password,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Admin user '{user.username}' created successfully."
            )
        )
