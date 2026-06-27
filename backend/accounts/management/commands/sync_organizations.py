"""
Populate accounts_organization from distinct non-null organization values
on the patient_info table. Safe to run repeatedly (upserts only).
"""
from django.core.management.base import BaseCommand
from django.db import ProgrammingError
from accounts.models import Organization
from patients.models import PatientInfo


class Command(BaseCommand):
    help = "Sync Organization table from patient_info.organization field"

    def handle(self, *args, **options):
        try:
            names = list(
                PatientInfo.objects
                .exclude(organization__isnull=True)
                .exclude(organization="")
                .values_list("organization", flat=True)
                .distinct()
                .order_by("organization")
            )
        except ProgrammingError as e:
            self.stdout.write(self.style.WARNING(
                f"Skipping org sync — patient_info.organization column not available: {e}"
            ))
            return

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
