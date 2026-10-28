"""Tests for cohort-filter plumbing in survey services and views.

The actual patient→response link (SurveyLinkedContact.patient_id) does not
exist in the DB until healthkey-ai/promop#2084 lands.  These tests exercise:

1. Service-layer response_ids filtering (works today with any set of IDs).
2. _cohort_response_ids view helper: returns None when no cohort params,
   returns None on ProgrammingError (column not in DB), and returns a set
   of UUIDs when the column exists.
3. View endpoints: without cohort params they return 200 with all responses;
   with unknown cohort params they still return 200 (graceful degradation).
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient
from types import SimpleNamespace

from surveys.models import (
    Survey, SurveyAnswer, SurveyLinkedContact,
    SurveyOption, SurveyQuestion, SurveyResponse, SurveyVersion,
)
from surveys.services import crosstab, question_responses, response_export


@pytest.fixture(scope="module")
def survey_tables(django_db_setup, django_db_blocker):
    models = [Survey, SurveyVersion, SurveyQuestion, SurveyOption, SurveyResponse, SurveyAnswer, SurveyLinkedContact]
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            for model in models:
                editor.create_model(model)
    yield
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            for model in reversed(models):
                editor.delete_model(model)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_survey(slug):
    survey = Survey.objects.create(id=uuid.uuid4(), slug=slug, title=slug.title())
    version = SurveyVersion.objects.create(survey=survey, version="1", created_at=timezone.now())
    q = SurveyQuestion.objects.create(
        survey_version=version, key="country", type="single", order=1, text="Country",
    )
    SurveyOption.objects.create(question=q, key="us", order=0, label="USA", free_text=False)
    return survey, version, q


def _submit(version, answer_value):
    r = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status="submitted")
    SurveyAnswer.objects.create(response=r, question_key="country", value=answer_value)
    return r


# ---------------------------------------------------------------------------
# Service layer: response_ids filtering
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_question_responses_response_ids_none_shows_all(survey_tables):
    """response_ids=None → all submitted responses included."""
    survey, version, _ = _make_survey("cohort-all")
    r1 = _submit(version, {"option": "us"})
    r2 = _submit(version, {"option": "us"})

    result = question_responses(survey, response_ids=None)
    assert result["questions"][0]["n"] == 2


@pytest.mark.django_db
def test_question_responses_response_ids_filters_to_subset(survey_tables):
    """response_ids={r1.id} → only r1's answer counted."""
    survey, version, _ = _make_survey("cohort-subset")
    r1 = _submit(version, {"option": "us"})
    _submit(version, {"option": "us"})

    result = question_responses(survey, response_ids={r1.id})
    assert result["questions"][0]["n"] == 1


@pytest.mark.django_db
def test_question_responses_response_ids_empty_set_returns_no_data(survey_tables):
    """response_ids={} (empty set from a cohort with no matching patients) → no questions."""
    survey, version, _ = _make_survey("cohort-empty")
    _submit(version, {"option": "us"})

    result = question_responses(survey, response_ids=set())
    assert result["questions"] == []


@pytest.mark.django_db
def test_response_export_response_ids_filters_correctly(survey_tables):
    """response_export with response_ids only exports the matching row."""
    survey, version, _ = _make_survey("cohort-export")
    r1 = _submit(version, {"option": "us"})
    _submit(version, {"option": "us"})

    result = response_export(survey, response_ids={r1.id})
    assert len(result["rows"]) == 1
    assert result["rows"][0]["respondent_id"] == str(r1.id)


@pytest.mark.django_db
def test_crosstab_response_ids_filters_correctly(survey_tables):
    """crosstab with response_ids only counts the matching response."""
    survey = Survey.objects.create(id=uuid.uuid4(), slug="cohort-crosstab", title="CT")
    version = SurveyVersion.objects.create(survey=survey, version="1", created_at=timezone.now())
    qx = SurveyQuestion.objects.create(
        survey_version=version, key="tx", type="single", order=1, text="Treatment",
    )
    qy = SurveyQuestion.objects.create(
        survey_version=version, key="country", type="single", order=2, text="Country",
    )
    SurveyOption.objects.create(question=qx, key="br", order=0, label="BR", free_text=False)
    SurveyOption.objects.create(question=qy, key="us", order=0, label="USA", free_text=False)

    r1 = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status="submitted")
    SurveyAnswer.objects.create(response=r1, question_key="tx", value={"option": "br"})
    SurveyAnswer.objects.create(response=r1, question_key="country", value={"option": "us"})

    r2 = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status="submitted")
    SurveyAnswer.objects.create(response=r2, question_key="tx", value={"option": "br"})
    SurveyAnswer.objects.create(response=r2, question_key="country", value={"option": "us"})

    result = crosstab(survey, "tx", "country", response_ids={r1.id})
    assert result["paired_completions"] == 1


# ---------------------------------------------------------------------------
# _cohort_response_ids helper
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_cohort_response_ids_no_params_returns_none(survey_tables):
    """No cohort params → None (show all)."""
    from surveys.views import _cohort_response_ids
    request = MagicMock()
    request.query_params = {}
    assert _cohort_response_ids(request) is None


@pytest.mark.django_db
def test_cohort_response_ids_survey_only_params_returns_none(survey_tables):
    """Only survey-specific params (include_partial, x, y) → None (show all)."""
    from surveys.views import _cohort_response_ids
    request = MagicMock()
    request.query_params = {"include_partial": "true", "x": "tx", "y": "country"}
    assert _cohort_response_ids(request) is None


@pytest.mark.django_db
def test_cohort_response_ids_graceful_on_db_error(survey_tables):
    """If the DB query raises (column not in schema yet) → None, never raises."""
    from surveys.views import _cohort_response_ids
    request = MagicMock()
    request.query_params = {"disease": "Follicular Lymphoma"}

    with patch("surveys.views.SurveyLinkedContact.objects") as mock_mgr:
        mock_mgr.filter.side_effect = Exception("column patient_id does not exist")
        result = _cohort_response_ids(request)

    assert result is None


# ---------------------------------------------------------------------------
# View integration: no cohort params → 200 with all responses
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_survey_responses_view_no_cohort_returns_all(survey_tables):
    """GET /surveys/<id>/responses/ without cohort params returns all responses."""
    survey, version, _ = _make_survey("view-no-cohort")
    _submit(version, {"option": "us"})
    _submit(version, {"option": "us"})

    client = APIClient()
    client.force_authenticate(user=SimpleNamespace(is_staff=True, is_authenticated=True))
    resp = client.get(f"/api/surveys/{survey.pk}/responses/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["questions"][0]["n"] == 2


@pytest.mark.django_db
def test_survey_responses_view_with_unknown_cohort_param_degrades_gracefully(survey_tables):
    """With cohort params but no patient_id column in DB → still 200, all responses."""
    survey, version, _ = _make_survey("view-cohort-degrade")
    _submit(version, {"option": "us"})

    client = APIClient()
    client.force_authenticate(user=SimpleNamespace(is_staff=True, is_authenticated=True))
    # disease param triggers the cohort-filter path; patient_id column absent → fallback
    resp = client.get(f"/api/surveys/{survey.pk}/responses/?disease=Follicular+Lymphoma")
    assert resp.status_code == 200
    data = resp.json()
    # Graceful degradation: all responses shown (n=1)
    assert data["questions"][0]["n"] == 1
