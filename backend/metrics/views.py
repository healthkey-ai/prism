from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.utils import apply_org_scope
from cohorts.filters import apply_cohort_filters
from metrics.services import (
    response_rates,
    treatment_patterns,
    treatment_pathways,
    demographics,
    staging,
    labs,
    treatment_duration,
    survival,
    ttnt,
    switching,
    subgroup_survival,
    pathway_sunburst,
    dor,
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def metrics(request):
    qs = apply_cohort_filters(request)

    qs, err = apply_org_scope(qs, request.user)
    if err:
        return err

    count = qs.count()
    if count == 0:
        return Response({"cohort": {"count": 0}})

    return Response({
        "cohort":              {"count": count},
        "response_rates":      response_rates.compute(qs),
        "treatment_patterns":  treatment_patterns.compute(qs),
        "treatment_pathways":  treatment_pathways.compute(qs),
        "demographics":        demographics.compute(qs),
        "staging":             staging.compute(qs),
        "labs":                labs.compute(qs),
        "treatment_duration":  treatment_duration.compute(qs),
        "survival":            survival.compute(qs),
        "ttnt":                ttnt.compute(qs),
        "switching":           switching.compute(qs),
        "subgroup_survival":   subgroup_survival.compute(qs),
        "pathway_sunburst":    pathway_sunburst.compute(qs),
        "dor":                 dor.compute(qs),
    })
