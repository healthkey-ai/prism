from django.db import connection, transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .models import Survey, SurveyLinkedContact
from .services import crosstab, question_catalog, question_responses, response_export, survey_catalog

# Query params that are survey-specific and should not be treated as cohort filters.
_SURVEY_PARAMS = frozenset({"include_partial", "x", "y"})


def _patient_link_available():
    """Whether PROlog's linked-contact table carries the patient link (patient_id).

    Until it does, survey responses cannot be matched to a clinical cohort, so
    cohort filters say nothing about them. Checked by introspection on each call,
    so a deployment that later adds the column picks it up without a restart.
    """
    try:
        with connection.cursor() as cursor:
            columns = connection.introspection.get_table_description(
                cursor, SurveyLinkedContact._meta.db_table
            )
    except Exception:
        return False
    return any(column.name == "patient_id" for column in columns)


def _cohort_response_ids(request):
    """Return SurveyResponse IDs belonging to the active cohort, or None.

    Returns None when:
    - No cohort filter params are present in the request (show all responses).
    - The patient_id column is not yet in the DB (graceful degradation until
      healthkey-ai/promop#2084 adds it to prolog_surveys_surveylinkedcontact).
    - The patient_id column exists but has no data yet (linkage not yet
      populated — degrade gracefully rather than returning an empty result).

    When the schema is in place and linkages exist, returns a (possibly empty)
    set of UUIDs so that callers can restrict their response queryset to cohort
    members.
    """
    cohort_params = {k for k in request.query_params if k not in _SURVEY_PARAMS}
    if not cohort_params:
        return None
    if not _patient_link_available():
        # Checked up front, not left to the query below failing: when the cohort
        # has no patients, `patient_id__in=[]` is short-circuited by Django and
        # never reaches the database, so it would return an empty set and hide
        # every response instead of falling back to all of them.
        return None
    try:
        # Wrap in a savepoint so any DB error (e.g. missing table in tests, or
        # patient_id column not yet in schema) rolls back only the inner work
        # without aborting the outer request transaction.
        with transaction.atomic():
            from accounts.utils import apply_org_scope
            from cohorts.filters import apply_cohort_filters
            from patients.models import PatientInfo

            # If no patient_id linkages exist at all, the feature is not yet
            # populated for this deployment — fall back to all responses.
            if not SurveyLinkedContact.objects.filter(
                patient_id__isnull=False
            ).exists():
                return None

            base_qs, _ = apply_org_scope(PatientInfo.objects.all(), request.user)
            filtered_qs = apply_cohort_filters(request, qs=base_qs)
            patient_ids = list(filtered_qs.values_list("id", flat=True))
            return set(
                SurveyLinkedContact.objects.filter(
                    patient_id__in=patient_ids
                ).values_list("response_id", flat=True)
            )
    except Exception:
        # Degrade gracefully: return None (all responses) until the patient_id
        # column is mirrored from PROMOP (healthkey-ai/promop#2084).
        return None


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
def survey_responses(request, survey_id):
    survey = Survey.objects.filter(pk=survey_id).first()
    if survey is None:
        return Response({"detail": "Survey not found."}, status=status.HTTP_404_NOT_FOUND)
    include_partial = request.query_params.get("include_partial", "").lower() in ("1", "true")
    response_ids = _cohort_response_ids(request)
    return Response(question_responses(survey, include_partial=include_partial, response_ids=response_ids))


@api_view(["GET"])
@permission_classes([IsAdminUser])
def survey_responses_export(request, survey_id):
    survey = Survey.objects.filter(pk=survey_id).first()
    if survey is None:
        return Response({"detail": "Survey not found."}, status=status.HTTP_404_NOT_FOUND)
    include_partial = request.query_params.get("include_partial", "").lower() in ("1", "true")
    response_ids = _cohort_response_ids(request)
    return Response(response_export(survey, include_partial=include_partial, response_ids=response_ids))


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
    include_partial = request.query_params.get("include_partial", "").lower() in ("1", "true")
    response_ids = _cohort_response_ids(request)
    return Response(crosstab(survey, x_key, y_key, include_partial=include_partial, response_ids=response_ids))
