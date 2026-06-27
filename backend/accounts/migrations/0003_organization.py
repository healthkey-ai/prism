from django.db import migrations, models


def seed_abc_foundation(apps, schema_editor):
    Organization = apps.get_model("accounts", "Organization")
    Organization.objects.get_or_create(
        name="ABC Foundation",
        defaults={"allowed_email_domain": ""},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_userprofile"),
    ]

    operations = [
        migrations.CreateModel(
            name="Organization",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255, unique=True)),
                ("allowed_email_domain", models.CharField(blank=True, default="", max_length=255)),
            ],
            options={
                "db_table": "accounts_organization",
                "ordering": ["name"],
            },
        ),
        migrations.RunPython(seed_abc_foundation, reverse_code=migrations.RunPython.noop),
    ]
