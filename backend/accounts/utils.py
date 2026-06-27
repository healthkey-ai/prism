"""Shared utilities for organisation-scoped querysets."""
from rest_framework.response import Response
from rest_framework import status

from .models import UserProfile


_NO_ORG_RESPONSE = Response(
    {"detail": "No organisation assigned. Contact your administrator."},
    status=status.HTTP_403_FORBIDDEN,
)


def apply_org_scope(qs, user):
    """
    Restrict *qs* to the user's organisation unless they have Staff role.

    Returns (scoped_qs, error_response_or_None).
    If error_response is not None, the caller should return it immediately.
    Staff users receive the original queryset unmodified.
    """
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        return None, _NO_ORG_RESPONSE

    if profile.role == UserProfile.ROLE_STAFF:
        return qs, None  # Staff see all orgs

    if not profile.organization:
        return None, _NO_ORG_RESPONSE

    return qs.filter(organization__name=profile.organization), None
