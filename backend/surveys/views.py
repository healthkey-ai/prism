from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from accounts.permissions import IsStaffOrOrgAnalyst
from accounts.utils import get_analytics_org_ids
from .models import Survey
from .services import crosstab, question_catalog, survey_catalog


def _visible_surveys(user):
    """Staff see every survey; org_admin and analyst users only their orgs' own."""
    if getattr(user, "is_staff", False) is True:
        return Survey.objects.all()
    return Survey.objects.filter(ownership__organization_id__in=get_analytics_org_ids(user))


def _visible_survey(request, survey_id):
    # Another org's survey answers 404, the same as one that does not exist.
    return _visible_surveys(request.user).filter(pk=survey_id).first()


@api_view(["GET"])
@permission_classes([IsStaffOrOrgAnalyst])
def surveys(request):
    return Response(survey_catalog(_visible_surveys(request.user)))


@api_view(["GET"])
@permission_classes([IsStaffOrOrgAnalyst])
def questions(request, survey_id):
    survey = _visible_survey(request, survey_id)
    if survey is None:
        return Response({"detail": "Survey not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response(question_catalog(survey))


@api_view(["GET"])
@permission_classes([IsStaffOrOrgAnalyst])
def survey_crosstab(request, survey_id):
    survey = _visible_survey(request, survey_id)
    if survey is None:
        return Response({"detail": "Survey not found."}, status=status.HTTP_404_NOT_FOUND)
    x_key = request.query_params.get("x", "")
    y_key = request.query_params.get("y", "")
    available = {q["key"] for q in question_catalog(survey)}
    if not x_key or not y_key or x_key == y_key or x_key not in available or y_key not in available:
        return Response({"detail": "Choose two different available questions."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(crosstab(survey, x_key, y_key))
