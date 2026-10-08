import uuid
from types import SimpleNamespace

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from surveys.models import Survey, SurveyAnswer, SurveyOption, SurveyQuestion, SurveyResponse, SurveyVersion
from surveys.services import crosstab, map_fl_treatment, question_catalog, survey_catalog


@pytest.fixture(scope="module")
def survey_tables(django_db_setup, django_db_blocker):
    # These are unmanaged PROMOP mirrors, so create only their tables in the
    # isolated Django test database. Never use the shared DATABASE_URL here.
    models = [Survey, SurveyVersion, SurveyQuestion, SurveyOption, SurveyResponse, SurveyAnswer]
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


def test_ranking_answers_keep_their_positions():
    from surveys.services import _labels, eligible

    question = SimpleNamespace(
        type="ranking", text="Rank outcomes",
        options=SimpleNamespace(all=lambda: [
            SimpleNamespace(key="a", label="Remission"),
            SimpleNamespace(key="b", label="Fewer visits"),
        ]),
    )
    assert eligible(question)
    assert _labels(question, {"order": ["b", "a"]}) == ["1: Fewer visits", "2: Remission"]


@pytest.mark.parametrize("type_, value", [("number", 42), ("date", "2026-01-02")])
def test_structured_values_remain_eligible(type_, value):
    from surveys.services import _labels, eligible

    question = SimpleNamespace(type=type_, text="Answer", options=SimpleNamespace(all=lambda: []))
    assert eligible(question)
    assert _labels(question, {type_: value}) == [str(value)]


@pytest.mark.django_db
def test_numeric_scale_summarizes_paired_submitted_answers(survey_tables):
    survey = Survey.objects.create(id=uuid.uuid4(), slug="scale-demo", title="Scale demo")
    version = SurveyVersion.objects.create(survey=survey, version="1", created_at=timezone.now())
    category = SurveyQuestion.objects.create(survey_version=version, key="group", type="single",
                                             order=1, text="Group")
    SurveyQuestion.objects.create(survey_version=version, key="score", type="scale",
                                  order=2, text="Score")
    SurveyOption.objects.create(question=category, key="a", order=0, label="A", free_text=False)
    SurveyOption.objects.create(question=category, key="b", order=1, label="B", free_text=False)

    for label, score, status in [("a", 1, "submitted"), ("a", 3, "submitted"),
                                 ("a", 5, "submitted"), ("b", 0, "submitted"),
                                 ("a", 100, "in_progress")]:
        response = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status=status)
        SurveyAnswer.objects.create(response=response, question_key="group", value={"option": label})
        SurveyAnswer.objects.create(response=response, question_key="score", value={"value": score})

    result = crosstab(survey, "group", "score")
    assert result["paired_completions"] == 4
    assert result["cells"] == []
    assert result["numeric_summaries"] == [{"axis": "y", "groups": [
        {"label": "A", "n": 3, "mean": 3, "sd": 2},
        {"label": "B", "n": 1, "mean": 0, "sd": None},
    ]}]
    inverted = crosstab(survey, "score", "group")
    assert inverted["numeric_summaries"] == [{"axis": "x", "groups": result["numeric_summaries"][0]["groups"]}]


@pytest.mark.django_db
def test_two_numeric_questions_use_only_paired_answers(survey_tables):
    survey = Survey.objects.create(id=uuid.uuid4(), slug="two-numbers", title="Two numbers")
    version = SurveyVersion.objects.create(survey=survey, version="1", created_at=timezone.now())
    SurveyQuestion.objects.create(survey_version=version, key="x", type="number", order=1, text="X")
    SurveyQuestion.objects.create(survey_version=version, key="y", type="scale", order=2, text="Y")
    for x, y in [(2, 1), (4, 5), (8, None)]:
        response = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status="submitted")
        SurveyAnswer.objects.create(response=response, question_key="x", value={"number": x})
        if y is not None:
            SurveyAnswer.objects.create(response=response, question_key="y", value={"value": y})
    result = crosstab(survey, "x", "y")
    assert result["paired_completions"] == 2
    assert result["numeric_summaries"] == [
        {"axis": "x", "groups": [{"label": "All paired responses", "n": 2,
                                   "mean": 3, "sd": pytest.approx(2 ** 0.5)}]},
        {"axis": "y", "groups": [{"label": "All paired responses", "n": 2,
                                   "mean": 3, "sd": pytest.approx(8 ** 0.5)}]},
    ]
