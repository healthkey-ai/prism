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
    Return the sorted list of org names this user may see aggregate data for.

    Access is granted via three mechanisms:
      - Public orgs: organizations with public_data=True are visible to all
        authenticated users regardless of their own org assignment.
      - Org-to-org trust: OrgTrust(granting_org=X, trusted_org=user's org)
        → user can see org X's patients
      - Domain trust: OrgTrust(granting_org=X, trusted_domain='example.com')
        → users with @example.com email can see org X's patients

    The user's own org is always included (if set).
    Do not call for ROLE_STAFF users — apply_org_scope handles that path
    by returning the queryset unmodified.
    """
    from .promop_models import PromopOrganization, PromopOrgTrust

    # Public orgs are visible to every authenticated user
    public_names: set[str] = set(
        PromopOrganization.objects.filter(public_data=True, is_active=True)
        .values_list("name", flat=True)
    )

    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return sorted(public_names)

    if not profile.organization:
        return sorted(public_names)

    own_name = profile.organization
    visible: set[str] = {own_name} | public_names

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

    - ROLE_STAFF           → unrestricted
    - Any authenticated user → filtered to get_visible_org_names(user), which
                               always includes public orgs plus the user's own
                               org and any trust-granted orgs.
    """
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return None, _NO_ORG_RESPONSE

    if profile.role == UserProfile.ROLE_STAFF:
        return qs, None  # staff see everything

    visible = get_visible_org_names(user)
    if not visible:
        return None, _NO_ORG_RESPONSE

    return qs.filter(organization__name__in=visible), None
