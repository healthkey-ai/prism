from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .models import Survey
from .services import crosstab, question_catalog, survey_catalog


@api_view(["GET"])
@permission_classes([IsAdminUser])
def surveys(request):
    return Response(survey_catalog())


@api_view(["GET"])
@permission_classes([IsAdminUser])
def questions(request, survey_id):
    survey = Survey.objects.filter(pk=survey_id).first()
    if survey is None:
        return Response({"detail": "Survey not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response(question_catalog(survey))


@api_view(["GET"])
@permission_classes([IsAdminUser])
def survey_crosstab(request, survey_id):
    survey = Survey.objects.filter(pk=survey_id).first()
    if survey is None:
        return Response({"detail": "Survey not found."}, status=status.HTTP_404_NOT_FOUND)
    x_key = request.query_params.get("x", "")
    y_key = request.query_params.get("y", "")
    available = {q["key"] for q in question_catalog(survey)}
    if not x_key or not y_key or x_key == y_key or x_key not in available or y_key not in available:
        return Response({"detail": "Choose two different available questions."}, status=status.HTTP_400_BAD_REQUEST)
    return Response(crosstab(survey, x_key, y_key))
