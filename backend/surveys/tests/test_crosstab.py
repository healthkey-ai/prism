import uuid
from types import SimpleNamespace

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from surveys.models import Survey, SurveyAnswer, SurveyOption, SurveyQuestion, SurveyResponse, SurveyVersion
from surveys.services import crosstab, map_fl_treatment, question_catalog, survey_catalog


@pytest.fixture
def survey_tables():
    # These are unmanaged PROMOP mirrors, so create only their tables in the
    # isolated Django test database. Never use the shared DATABASE_URL here.
    models = [Survey, SurveyVersion, SurveyQuestion, SurveyOption, SurveyResponse, SurveyAnswer]
    with connection.schema_editor() as editor:
        for model in models:
            editor.create_model(model)
    yield
    with connection.schema_editor() as editor:
        for model in reversed(models):
            editor.delete_model(model)


@pytest.mark.django_db(transaction=True)
def test_submitted_multiselect_crosstab_and_freeform_exclusion(survey_tables):
    survey = Survey.objects.create(id=uuid.uuid4(), slug="fl", title="FL survey")
    version = SurveyVersion.objects.create(survey=survey, version="1", created_at=timezone.now())
    x = SurveyQuestion.objects.create(survey_version=version, key="treatments", type="multi", order=1,
                                      text="Which treatments have you had?")
    y = SurveyQuestion.objects.create(survey_version=version, key="country", type="single", order=2,
                                      text="Country")
    SurveyQuestion.objects.create(survey_version=version, key="story", type="text", order=3,
                                  text="Tell us your story")
    SurveyOption.objects.create(question=x, key="br", order=0, label="BR", free_text=False)
    SurveyOption.objects.create(question=x, key="other", order=1, label="Other", free_text=True)
    SurveyOption.objects.create(question=y, key="gb", order=0, label="United Kingdom", free_text=False)
    submitted = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status="submitted")
    SurveyAnswer.objects.create(response=submitted, question_key="treatments",
                                value={"options": ["br", "other"], "other_text": "R-CHOP"})
    SurveyAnswer.objects.create(response=submitted, question_key="country", value={"option": "gb"})
    draft = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status="in_progress")
    SurveyAnswer.objects.create(response=draft, question_key="treatments", value={"options": ["br"]})
    SurveyAnswer.objects.create(response=draft, question_key="country", value={"option": "gb"})

    assert survey_catalog() == [{"id": str(survey.pk), "title": "FL survey", "completions": 1}]
    assert [q["key"] for q in question_catalog(survey)] == ["treatments", "country"]
    result = crosstab(survey, "treatments", "country")
    assert result["paired_completions"] == 1
    assert result["cells"] == [
        {"x": "BR", "y": "United Kingdom", "count": 1},
        {"x": "R-CHOP", "y": "United Kingdom", "count": 1},
    ]

    client = APIClient()
    client.force_authenticate(user=SimpleNamespace(is_staff=False, is_authenticated=True))
    assert client.get(f"/api/surveys/{survey.pk}/crosstab/?x=treatments&y=country").status_code == 403
    client.force_authenticate(user=SimpleNamespace(is_staff=True, is_authenticated=True))
    assert client.get(f"/api/surveys/{survey.pk}/crosstab/?x=story&y=country").status_code == 400
    assert client.get(f"/api/surveys/{survey.pk}/crosstab/?x=treatments&y=country").json() == result


@pytest.mark.parametrize("description, expected", [
    ("R2", "Lenalidomide and Rituximab (R2)"),
    ("BR", "Bendamustine and Rituximab (BR)"),
    ("R-CHOP", "R-CHOP"),
    ("chemotherapy", None),
    ("rituximab or obinutuzumab", None),
    ("", None),
])
def test_treatment_mapping_is_conservative(description, expected):
    assert map_fl_treatment(description) == expected
