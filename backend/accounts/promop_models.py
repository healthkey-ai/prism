"""
Read-only unmanaged mirrors of PROMOP's shared-DB tables.

Prism and PROMOP share the same PostgreSQL database. These models let Prism
read PROMOP's organisation and trust tables without owning or migrating them.
"""
from django.db import models


class PromopOrganization(models.Model):
    """Mirror of PROMOP's `organization` table."""
    name        = models.CharField(max_length=200)
    slug        = models.SlugField(max_length=60, unique=True)
    is_active   = models.BooleanField(default=True)
    public_data = models.BooleanField(default=False)

    class Meta:
        managed  = False
        db_table = "organization"

    def __str__(self):
        return self.name


class PromopOrgTrust(models.Model):
    """
    Mirror of PROMOP's `org_trust` table.

    Each row means: granting_org's patient data is accessible to users of
    trusted_org (org-to-org mode) or to users whose email matches
    trusted_domain (domain mode). Exactly one of trusted_org / trusted_domain
    is set per row (enforced by a DB CHECK constraint in PROMOP).
    """
    granting_org  = models.ForeignKey(
        PromopOrganization, on_delete=models.DO_NOTHING,
        db_column="granting_org_id", related_name="trusts_granted",
    )
    trusted_org   = models.ForeignKey(
        PromopOrganization, on_delete=models.DO_NOTHING,
        db_column="trusted_org_id", related_name="trusted_by",
        null=True, blank=True,
    )
    trusted_domain = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        managed  = False
        db_table = "org_trust"
