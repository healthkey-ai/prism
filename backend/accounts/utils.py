"""Shared utilities for organisation-scoped querysets."""
from rest_framework.response import Response
from rest_framework import status

from .models import UserProfile


_NO_ORG_RESPONSE = Response(
    {"detail": "No organisation assigned. Contact your administrator."},
    status=status.HTTP_403_FORBIDDEN,
)


def get_visible_org_names(user) -> list[str]:
    """
    Return the sorted list of PatientInfo.organization values this user may see.

    Access is granted via two mechanisms (both read from PROMOP's shared tables):
      - Org-to-org trust: OrgTrust(granting_org=X, trusted_org=user's org)
        → user can see org X's patients
      - Domain trust: OrgTrust(granting_org=X, trusted_domain='example.com')
        → users with @example.com email can see org X's patients

    The user's own org is always included.
    Returns [] when the user has no org or no profile.

    Do not call for ROLE_STAFF users — apply_org_scope handles that path
    by returning the queryset unmodified.
    """
    from .promop_models import PromopOrganization, PromopOrgTrust

    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return []

    if not profile.organization:
        return []

    own_name = profile.organization
    visible: set[str] = {own_name}

    # ── org-to-org trusts ─────────────────────────────────────────────────────
    try:
        own_org = PromopOrganization.objects.get(name=own_name, is_active=True)
        for name in PromopOrgTrust.objects.filter(
            trusted_org=own_org,
            granting_org__is_active=True,
        ).values_list("granting_org__name", flat=True):
            visible.add(name)
    except PromopOrganization.DoesNotExist:
        pass  # org not registered in PROMOP — user sees only their own data

    # ── domain trusts ─────────────────────────────────────────────────────────
    email = getattr(user, "email", "") or ""
    if "@" in email:
        user_domain = email.split("@")[1].lower()
        for name in PromopOrgTrust.objects.filter(
            trusted_domain__iexact=user_domain,
            granting_org__is_active=True,
        ).values_list("granting_org__name", flat=True):
            visible.add(name)

    return sorted(visible)


def apply_org_scope(qs, user):
    """
    Restrict *qs* to the organisations the user is allowed to see.

    Returns (scoped_qs, error_response_or_None).
    If error_response is not None, the caller should return it immediately.

    - ROLE_STAFF → unrestricted (original qs returned unchanged)
    - All others  → filtered to get_visible_org_names(user), which follows
                    PROMOP's OrgTrust relationships so multi-org users
                    (e.g. HealthTree Trust) see all their accessible orgs.
    """
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return None, _NO_ORG_RESPONSE

    if profile.role == UserProfile.ROLE_STAFF:
        return qs, None  # staff see everything

    if not profile.organization:
        return None, _NO_ORG_RESPONSE

    visible = get_visible_org_names(user)
    if not visible:
        return None, _NO_ORG_RESPONSE

    return qs.filter(organization__in=visible), None
