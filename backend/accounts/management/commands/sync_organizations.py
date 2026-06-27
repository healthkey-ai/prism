"""
Populate accounts_organization from the source organization table.
Safe to run repeatedly (upserts only).
"""
from django.core.management.base import BaseCommand
from accounts.models import Organization
from patients.models import SourceOrganization


class Command(BaseCommand):
    help = "Sync Organization table from source organization table"

    def handle(self, *args, **options):
        names = list(
            SourceOrganization.objects
            .values_list("name", flat=True)
            .order_by("name")
        )

        created_count = 0
        for name in names:
            _, created = Organization.objects.get_or_create(
                name=name,
                defaults={"allowed_email_domain": ""},
            )
            if created:
                created_count += 1
                self.stdout.write(f"  + {name}")

        self.stdout.write(self.style.SUCCESS(
            f"Done — {created_count} new org(s) added, "
            f"{len(names) - created_count} already present."
        ))
