from django.db import connection, transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from patients.models import PatientInfo
from .models import Survey, SurveyLinkedContact, SurveyResponse
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


def _participant_link_populated():
    """Whether any survey respondent is a PROMOP patient.

    PROlog records who answered in SurveyResponse.participant_id (the PROMOP
    person). A patient_record carries the same id in person_id, so a response
    belongs to a clinical cohort when its participant is one of the cohort's
    patients. Respondents minted for anonymous web submissions have no
    patient_record, so a deployment with only those has no usable link.
    """
    try:
        # Own savepoint: a deployment (or test database) without the patient
        # table must read as "no link", not abort the request transaction.
        with transaction.atomic():
            persons = PatientInfo.objects.exclude(person_id__isnull=True).values("person_id")
            return SurveyResponse.objects.filter(participant_id__in=persons).exists()
    except Exception:
        return False


def _contact_link_populated():
    """Whether the linked-contact table carries any patient_id (promop#2084)."""
    return _patient_link_available() and SurveyLinkedContact.objects.filter(
        patient_id__isnull=False
    ).exists()


def _cohort_response_ids(request):
    """Return SurveyResponse IDs belonging to the active cohort, or None.

    Returns None when:
    - No cohort filter params are present in the request (show all responses).
    - No response can be tied to a patient at all: no respondent's participant
      is a patient_record person, and the linked-contact patient_id column is
      absent or empty (healthkey-ai/promop#2084). Degrading to all responses is
      better than silently emptying every survey.

    Otherwise returns a (possibly empty) set of UUIDs: the responses whose
    participant is a cohort patient, plus any linked contacts pointing at one.
    """
    cohort_params = {k for k in request.query_params if k not in _SURVEY_PARAMS}
    if not cohort_params:
        return None
    try:
        # Wrap in a savepoint so any DB error (e.g. missing table in tests)
        # rolls back only the inner work without aborting the outer request
        # transaction.
        with transaction.atomic():
            from accounts.utils import apply_org_scope
            from cohorts.filters import apply_cohort_filters

            participant_link = _participant_link_populated()
            contact_link = _contact_link_populated()
            if not participant_link and not contact_link:
                return None

            base_qs, _ = apply_org_scope(PatientInfo.objects.all(), request.user)
            filtered_qs = apply_cohort_filters(request, qs=base_qs)
            response_ids = set()
            if participant_link:
                # Materialised, not a subquery: an empty cohort must yield an
                # empty set, and Django short-circuits `__in=[]` to nothing.
                person_ids = [
                    pid for pid in filtered_qs.values_list("person_id", flat=True) if pid is not None
                ]
                response_ids |= set(
                    SurveyResponse.objects.filter(
                        participant_id__in=person_ids
                    ).values_list("id", flat=True)
                )
            if contact_link:
                patient_ids = list(filtered_qs.values_list("id", flat=True))
                response_ids |= set(
                    SurveyLinkedContact.objects.filter(
                        patient_id__in=patient_ids
                    ).values_list("response_id", flat=True)
                )
            return response_ids
    except Exception:
        # Degrade gracefully: all responses rather than a misleading empty set.
        return None


@api_view(["GET"])
@permission_classes([IsAdminUser])
def surveys(request):
    return Response(survey_catalog(response_ids=_cohort_response_ids(request)))


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
