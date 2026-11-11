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


@pytest.mark.django_db
def test_cohort_response_ids_no_linkages_returns_none(survey_tables):
    """patient_id column exists but no rows have a non-null patient_id → None (show all).

    This is the FLF case: patient_id column is in the schema but linkage hasn't
    been populated yet.  Returning None degrades gracefully to all responses
    rather than silently returning an empty result set.
    """
    from surveys.views import _cohort_response_ids
    # Create a SurveyLinkedContact with no patient_id (null)
    survey, version, _ = _make_survey("no-linkage")
    r = _submit(version, {"option": "us"})
    SurveyLinkedContact.objects.create(response=r, email="test@example.com")

    request = MagicMock()
    request.query_params = {"disease": "Follicular Lymphoma"}
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


# ---------------------------------------------------------------------------
# No patient link: cohort filters must not hide responses
# ---------------------------------------------------------------------------

def _empty_cohort():
    """A cohort with no patients, as PatientInfo filtering returns on a
    database whose survey respondents have no clinical record."""
    qs = MagicMock()
    qs.values_list.return_value = []
    return qs


@pytest.mark.django_db
def test_cohort_ignored_when_responses_cannot_be_linked(survey_tables):
    """The real-world case: cohort params set, the cohort is empty, and the link
    column is absent. Must be None (all responses), not an empty set."""
    from surveys.views import _cohort_response_ids
    request = MagicMock()
    request.query_params = {"disease": "Some Disease"}
    with patch("surveys.views._patient_link_available", return_value=False), \
            patch("cohorts.filters.apply_cohort_filters") as cohort:
        assert _cohort_response_ids(request) is None
        cohort.assert_not_called()


@pytest.mark.django_db
def test_empty_cohort_with_patient_link_returns_no_responses(survey_tables):
    """With the link in place, an empty cohort really does mean no responses."""
    from surveys.views import _cohort_response_ids
    # Linkage is populated: one respondent is linked to a patient, who is not in
    # the cohort. Without a linked row, the no-linkage fallback returns None.
    _, version, _ = _make_survey("linked-empty-cohort")
    linked = _submit(version, {"option": "us"})
    SurveyLinkedContact.objects.create(response=linked, email="x@example.com", patient_id=uuid.uuid4())

    request = MagicMock()
    request.query_params = {"disease": "Some Disease"}
    with patch("surveys.views._patient_link_available", return_value=True), \
            patch("accounts.utils.apply_org_scope", side_effect=lambda qs, user: (qs, None)), \
            patch("cohorts.filters.apply_cohort_filters", return_value=_empty_cohort()):
        assert _cohort_response_ids(request) == set()


@pytest.mark.django_db
def test_patient_link_available_reads_the_table(survey_tables):
    from surveys.views import _patient_link_available
    # The test table is created from the mirror, which declares patient_id.
    assert _patient_link_available() is True
    with patch("surveys.views.connection.introspection.get_table_description",
               return_value=[SimpleNamespace(name="id"), SimpleNamespace(name="email")]):
        assert _patient_link_available() is False
    with patch("surveys.views.connection.introspection.get_table_description",
               side_effect=Exception("no such table")):
        assert _patient_link_available() is False


# ---------------------------------------------------------------------------
# Participant link: SurveyResponse.participant_id -> patient_record.person_id
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def patient_tables(django_db_setup, django_db_blocker):
    from patients.models import PatientInfo, SourceOrganization
    models = [SourceOrganization, PatientInfo]
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            for model in models:
                editor.create_model(model)
    yield
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            for model in reversed(models):
                editor.delete_model(model)


def _patient(person_id, disease, org):
    from patients.models import PatientInfo
    return PatientInfo.objects.create(person_id=person_id, disease=disease, organization=org)


def _respond(version, participant_id):
    r = SurveyResponse.objects.create(
        id=uuid.uuid4(), survey_version=version, status="submitted", participant_id=participant_id,
    )
    SurveyAnswer.objects.create(response=r, question_key="country", value={"option": "us"})
    return r


@pytest.fixture
def two_org_respondents(survey_tables, patient_tables):
    """One FL respondent and one BC respondent, each a patient of a different org."""
    from patients.models import SourceOrganization
    fl_org = SourceOrganization.objects.create(name="SYNTHEA-FL", slug="synthea-fl")
    bc_org = SourceOrganization.objects.create(name="SYNTHEA-BC", slug="synthea-bc")
    _patient(101, "Follicular Lymphoma", fl_org)
    _patient(202, "Breast Cancer", bc_org)
    survey, version, _ = _make_survey("participant-link")
    fl_response = _respond(version, 101)
    bc_response = _respond(version, 202)
    return SimpleNamespace(survey=survey, fl=fl_response, bc=bc_response)


def _staff_request(**params):
    from urllib.parse import urlencode
    from django.http import QueryDict
    request = MagicMock()
    # A real QueryDict: apply_cohort_filters reads params with getlist().
    request.query_params = QueryDict(urlencode(params))
    request.user = SimpleNamespace(is_staff=True, is_authenticated=True)
    return request


@pytest.mark.django_db
def test_cohort_response_ids_follows_participant_link(two_org_respondents):
    """An org filter keeps only responses whose participant is one of the org's patients."""
    from surveys.views import _cohort_response_ids
    assert _cohort_response_ids(_staff_request(org="SYNTHEA-FL")) == {two_org_respondents.fl.id}
    assert _cohort_response_ids(_staff_request(org="SYNTHEA-BC")) == {two_org_respondents.bc.id}
    assert _cohort_response_ids(_staff_request(disease="Follicular Lymphoma")) == {two_org_respondents.fl.id}


@pytest.mark.django_db
def test_cohort_response_ids_empty_cohort_is_empty_when_participants_are_patients(two_org_respondents):
    """With respondents linked through their participant, a cohort nobody is in hides every response."""
    from surveys.views import _cohort_response_ids
    assert _cohort_response_ids(_staff_request(org="SYNTHEA-MM")) == set()


@pytest.mark.django_db
def test_cohort_response_ids_none_when_no_participant_is_a_patient(survey_tables, patient_tables):
    """Respondents minted for anonymous submissions have no patient record: no link, show all."""
    from surveys.views import _cohort_response_ids
    _, version, _ = _make_survey("anonymous-participants")
    _respond(version, 9001)
    assert _cohort_response_ids(_staff_request(org="SYNTHEA-FL")) is None


@pytest.mark.django_db
def test_survey_catalog_counts_completions_within_cohort(two_org_respondents):
    from surveys.services import survey_catalog
    survey_id = str(two_org_respondents.survey.pk)
    assert [(s["id"], s["completions"]) for s in survey_catalog()] == [(survey_id, 2)]
    assert [(s["id"], s["completions"]) for s in survey_catalog(response_ids={two_org_respondents.bc.id})] == [(survey_id, 1)]
    assert survey_catalog(response_ids=set()) == []


@pytest.mark.django_db
def test_surveys_and_responses_views_scope_to_org(two_org_respondents):
    """GET /surveys/?org=… lists cohort completions; /responses/ counts only cohort respondents."""
    client = APIClient()
    client.force_authenticate(user=SimpleNamespace(is_staff=True, is_authenticated=True))
    survey_id = two_org_respondents.survey.pk

    catalog = client.get("/api/surveys/?org=SYNTHEA-BC").json()
    assert [(s["id"], s["completions"]) for s in catalog] == [(str(survey_id), 1)]

    assert client.get(f"/api/surveys/{survey_id}/responses/?org=SYNTHEA-BC").json()["total_responses"] == 1
    assert client.get(f"/api/surveys/{survey_id}/responses/").json()["total_responses"] == 2
    assert client.get("/api/surveys/?org=SYNTHEA-MM").json() == []
