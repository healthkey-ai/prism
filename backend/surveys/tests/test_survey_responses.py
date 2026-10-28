import uuid
from unittest.mock import MagicMock

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient
from types import SimpleNamespace

from surveys.models import Survey, SurveyAnswer, SurveyLinkedContact, SurveyOption, SurveyQuestion, SurveyResponse, SurveyVersion
from surveys.services import question_responses, response_export


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


@pytest.mark.django_db
def test_question_responses_basic(survey_tables):
    survey = Survey.objects.create(id=uuid.uuid4(), slug="resp-basic", title="Response basic")
    version = SurveyVersion.objects.create(survey=survey, version="1", created_at=timezone.now())
    multi_q = SurveyQuestion.objects.create(
        survey_version=version, key="treatments", type="multi", order=1,
        text="Which treatments have you had?",
    )
    single_q = SurveyQuestion.objects.create(
        survey_version=version, key="country", type="single", order=2,
        text="Country",
    )
    # scale question — should be excluded (numeric)
    SurveyQuestion.objects.create(
        survey_version=version, key="score", type="scale", order=3, text="Score",
    )
    SurveyOption.objects.create(question=multi_q, key="br", order=0, label="BR", free_text=False)
    SurveyOption.objects.create(question=multi_q, key="rchop", order=1, label="R-CHOP", free_text=False)
    SurveyOption.objects.create(question=single_q, key="gb", order=0, label="United Kingdom", free_text=False)

    # submitted response
    submitted = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status="submitted")
    SurveyAnswer.objects.create(response=submitted, question_key="treatments", value={"options": ["br"]})
    SurveyAnswer.objects.create(response=submitted, question_key="country", value={"option": "gb"})
    SurveyAnswer.objects.create(response=submitted, question_key="score", value={"value": 5})

    result = question_responses(survey)
    assert result["total_responses"] == 1
    assert result["include_partial"] is False
    # scale excluded → only treatments + country
    assert len(result["questions"]) == 2
    q = next(q for q in result["questions"] if q["key"] == "treatments")
    assert q["n"] == 1
    assert q["options"] == [{"label": "BR", "count": 1, "pct": 100.0}]


@pytest.mark.django_db
def test_question_responses_include_partial(survey_tables):
    survey = Survey.objects.create(id=uuid.uuid4(), slug="resp-partial", title="Response partial")
    version = SurveyVersion.objects.create(survey=survey, version="1", created_at=timezone.now())
    q = SurveyQuestion.objects.create(
        survey_version=version, key="country", type="single", order=1, text="Country",
    )
    SurveyOption.objects.create(question=q, key="us", order=0, label="USA", free_text=False)

    submitted = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status="submitted")
    SurveyAnswer.objects.create(response=submitted, question_key="country", value={"option": "us"})

    partial = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status="in_progress")
    SurveyAnswer.objects.create(response=partial, question_key="country", value={"option": "us"})

    # Default (include_partial=False): only submitted
    result = question_responses(survey, include_partial=False)
    assert result["total_responses"] == 1
    assert result["include_partial"] is False
    assert result["questions"][0]["n"] == 1

    # include_partial=True: both responses
    result_p = question_responses(survey, include_partial=True)
    assert result_p["total_responses"] == 2
    assert result_p["include_partial"] is True
    assert result_p["questions"][0]["n"] == 2
    assert result_p["questions"][0]["options"][0] == {"label": "USA", "count": 2, "pct": 100.0}


@pytest.mark.django_db
def test_question_responses_empty_queryset(survey_tables):
    survey = Survey.objects.create(id=uuid.uuid4(), slug="resp-empty", title="Response empty")
    version = SurveyVersion.objects.create(survey=survey, version="1", created_at=timezone.now())
    SurveyQuestion.objects.create(
        survey_version=version, key="country", type="single", order=1, text="Country",
    )
    # No responses at all
    result = question_responses(survey)
    assert result["total_responses"] == 0
    # question_catalog returns empty (no submitted responses) so questions list is empty
    assert result["questions"] == []


@pytest.mark.django_db
def test_question_responses_multiple_options_sorted_by_count(survey_tables):
    survey = Survey.objects.create(id=uuid.uuid4(), slug="resp-sort", title="Response sort")
    version = SurveyVersion.objects.create(survey=survey, version="1", created_at=timezone.now())
    q = SurveyQuestion.objects.create(
        survey_version=version, key="treatment", type="single", order=1,
        text="Treatment",
    )
    SurveyOption.objects.create(question=q, key="br", order=0, label="BR", free_text=False)
    SurveyOption.objects.create(question=q, key="rchop", order=1, label="R-CHOP", free_text=False)

    for treatment, count in [("br", 3), ("rchop", 1)]:
        for _ in range(count):
            r = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status="submitted")
            SurveyAnswer.objects.create(response=r, question_key="treatment", value={"option": treatment})

    result = question_responses(survey)
    assert len(result["questions"]) == 1
    opts = result["questions"][0]["options"]
    # sorted by count descending
    assert opts[0]["label"] == "BR"
    assert opts[0]["count"] == 3
    assert opts[0]["pct"] == 75.0
    assert opts[1]["label"] == "R-CHOP"
    assert opts[1]["count"] == 1
    assert opts[1]["pct"] == 25.0


@pytest.mark.django_db
def test_response_export_no_email_by_default(survey_tables):
    """Default export omits email; SurveyLinkedContact is never joined."""
    survey = Survey.objects.create(id=uuid.uuid4(), slug="resp-export-nomail", title="Response export nomail")
    version = SurveyVersion.objects.create(survey=survey, version="1", created_at=timezone.now())
    q = SurveyQuestion.objects.create(
        survey_version=version, key="treatment", type="single", order=1, text="Treatment",
    )
    SurveyOption.objects.create(question=q, key="br", order=0, label="BR", free_text=False)

    r1 = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status="submitted")
    SurveyAnswer.objects.create(response=r1, question_key="treatment", value={"option": "br"})
    r2 = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status="submitted")
    SurveyAnswer.objects.create(response=r2, question_key="treatment", value={"option": "br"})
    # Attach an email contact to r2 — should NOT appear in the export
    SurveyLinkedContact.objects.create(response=r2, email="user@example.com")

    result = response_export(survey)
    assert result["questions"] == [{"key": "treatment", "text": "Treatment"}]
    assert len(result["rows"]) == 2
    ids = {row["respondent_id"] for row in result["rows"]}
    assert str(r1.id) in ids
    assert str(r2.id) in ids
    # No row should carry an email key when include_email is False (default)
    for row in result["rows"]:
        assert "email" not in row
    row1 = next(row for row in result["rows"] if row["respondent_id"] == str(r1.id))
    assert row1["answers"]["treatment"] == "BR"


@pytest.mark.django_db
def test_response_export_include_email_returns_all_contacts(survey_tables):
    """include_email=True returns emails for all respondents with a linked contact.

    Consent-withdrawn filtering will be added once PROMOP adds the
    consent_withdrawn column (healthkey-ai/promop#2079).
    """
    survey = Survey.objects.create(id=uuid.uuid4(), slug="resp-export-email", title="Response export email")
    version = SurveyVersion.objects.create(survey=survey, version="1", created_at=timezone.now())
    q = SurveyQuestion.objects.create(
        survey_version=version, key="country", type="single", order=1, text="Country",
    )
    SurveyOption.objects.create(question=q, key="us", order=0, label="USA", free_text=False)

    r_with_email = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status="submitted")
    SurveyAnswer.objects.create(response=r_with_email, question_key="country", value={"option": "us"})
    SurveyLinkedContact.objects.create(response=r_with_email, email="alice@example.com")

    r_no_contact = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status="submitted")
    SurveyAnswer.objects.create(response=r_no_contact, question_key="country", value={"option": "us"})

    result = response_export(survey, include_email=True)
    assert len(result["rows"]) == 2
    by_id = {row["respondent_id"]: row for row in result["rows"]}

    assert by_id[str(r_with_email.id)]["email"] == "alice@example.com"
    assert by_id[str(r_no_contact.id)]["email"] == ""


def _staff_user(has_view_contacts=False):
    """Return a mock staff user; optionally grant surveys.view_contacts."""
    user = MagicMock()
    user.is_authenticated = True
    user.is_staff = True
    user.has_perm = lambda perm: perm == "surveys.view_contacts" and has_view_contacts
    return user


@pytest.mark.django_db
def test_export_include_email_requires_view_contacts_permission(survey_tables):
    """Staff without view_contacts perm receives 403 when include_email=true."""
    survey = Survey.objects.create(id=uuid.uuid4(), slug="resp-403", title="Resp 403")
    version = SurveyVersion.objects.create(survey=survey, version="1", created_at=timezone.now())
    q = SurveyQuestion.objects.create(
        survey_version=version, key="country", type="single", order=1, text="Country",
    )
    SurveyOption.objects.create(question=q, key="us", order=0, label="USA", free_text=False)

    client = APIClient()
    client.force_authenticate(user=_staff_user(has_view_contacts=False))
    resp = client.get(f"/api/surveys/{survey.pk}/responses/export/?include_email=true")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_export_include_email_allowed_for_view_contacts_user(survey_tables):
    """Staff with view_contacts perm receives emails in the response."""
    survey = Survey.objects.create(id=uuid.uuid4(), slug="resp-200", title="Resp 200")
    version = SurveyVersion.objects.create(survey=survey, version="1", created_at=timezone.now())
    q = SurveyQuestion.objects.create(
        survey_version=version, key="country", type="single", order=1, text="Country",
    )
    SurveyOption.objects.create(question=q, key="us", order=0, label="USA", free_text=False)
    r = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status="submitted")
    SurveyAnswer.objects.create(response=r, question_key="country", value={"option": "us"})
    SurveyLinkedContact.objects.create(response=r, email="alice@example.com")

    client = APIClient()
    client.force_authenticate(user=_staff_user(has_view_contacts=True))
    resp = client.get(f"/api/surveys/{survey.pk}/responses/export/?include_email=true")
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["email"] == "alice@example.com"


@pytest.mark.django_db
def test_survey_responses_api_view(survey_tables):
    survey = Survey.objects.create(id=uuid.uuid4(), slug="resp-api", title="Response API")
    version = SurveyVersion.objects.create(survey=survey, version="1", created_at=timezone.now())
    q = SurveyQuestion.objects.create(
        survey_version=version, key="country", type="single", order=1, text="Country",
    )
    SurveyOption.objects.create(question=q, key="us", order=0, label="USA", free_text=False)
    r = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status="submitted")
    SurveyAnswer.objects.create(response=r, question_key="country", value={"option": "us"})

    client = APIClient()
    client.force_authenticate(user=SimpleNamespace(is_staff=False, is_authenticated=True))
    assert client.get(f"/api/surveys/{survey.pk}/responses/").status_code == 403

    client.force_authenticate(user=SimpleNamespace(is_staff=True, is_authenticated=True))
    resp = client.get(f"/api/surveys/{survey.pk}/responses/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_responses"] == 1
    assert data["questions"][0]["key"] == "country"

    # Not found
    assert client.get(f"/api/surveys/{uuid.uuid4()}/responses/").status_code == 404
