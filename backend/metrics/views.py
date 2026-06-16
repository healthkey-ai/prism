from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import UserProfile
from cohorts.filters import apply_cohort_filters
from metrics.services import (
    response_rates,
    treatment_patterns,
    demographics,
    staging,
    labs,
    treatment_duration,
    survival,
    ttnt,
    switching,
    subgroup_survival,
    dor,
)


def _apply_org_scope(qs, user):
    """
    Restrict queryset to the user's organisation unless they have Staff role.
    Returns (scoped_qs, error_response_or_None).
    """
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        # No profile → no data (user must be set up by admin first)
        return None, Response({"cohort": {"count": 0}})

    if profile.role == UserProfile.ROLE_STAFF:
        return qs, None  # Staff see all orgs

    if not profile.organization:
        return None, Response({"cohort": {"count": 0}})

    return qs.filter(organization=profile.organization), None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def metrics(request):
    qs = apply_cohort_filters(request)

    qs, err = _apply_org_scope(qs, request.user)
    if err:
        return err

    count = qs.count()
    if count == 0:
        return Response({"cohort": {"count": 0}})

    return Response({
        "cohort":              {"count": count},
        "response_rates":      response_rates.compute(qs),
        "treatment_patterns":  treatment_patterns.compute(qs),
        "demographics":        demographics.compute(qs),
        "staging":             staging.compute(qs),
        "labs":                labs.compute(qs),
        "treatment_duration":  treatment_duration.compute(qs),
        "survival":            survival.compute(qs),
        "ttnt":                ttnt.compute(qs),
        "switching":           switching.compute(qs),
        "subgroup_survival":   subgroup_survival.compute(qs),
        "dor":                 dor.compute(qs),
    })
