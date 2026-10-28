"""Label resolution against definitions shaped the way PROlog stores them, and
the query shape that keeps it fast at realistic volume.

PROlog's stored definition nests questions inside sections
(``{"sections": [{"questions": [...]}]}``); there is no top-level
``questions`` list. These tests use that shape, and check that labelling many
answers neither selects the definition per row nor grows its query count with
the number of responses.
"""
import uuid

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from surveys.models import (
    Survey,
    SurveyAnswer,
    SurveyOption,
    SurveyQuestion,
    SurveyResponse,
    SurveyVersion,
)
from surveys.services import (
    _labels,
    _parse_definition,
    crosstab,
    question_catalog,
    question_responses,
)
from surveys.tests.test_definition_labels import _q

# A definition in PROlog's stored shape: questions inside sections.
SECTIONED = {
    "default_language": "en",
    "sections": [
        {
            "key": "s1",
            "questions": [
                {
                    "key": "picked",
                    "type": "multi",
                    "config": {},
                    "options": [
                        {"key": "alpha", "label": {"en": "Alpha option"}},
                        {"key": "beta", "label": {"en": "Beta option"}},
                    ],
                },
                {
                    "key": "most_recent",
                    "type": "single",
                    "config": {"options_from": "picked"},
                    "options": [{"key": "unsure", "label": {"en": "Not sure"}}],
                },
            ],
        },
        {
            "key": "s2",
            "questions": [
                {
                    "key": "grid",
                    "type": "matrix",
                    "config": {
                        "rows": [
                            {"key": "row_one", "label": {"en": "First row"}},
                            {"key": "row_two", "label": {"en": "Second row"}},
                        ],
                        "scale": {
                            "min": 1,
                            "max": 3,
                            "point_labels": [{"en": "Low"}, {"en": "Middle"}, {"en": "High"}],
                            "not_applicable": {"en": "Does not apply"},
                        },
                    },
                },
            ],
        },
    ],
}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def test_parse_finds_questions_inside_sections():
    lang, by_key = _parse_definition(SECTIONED)
    assert lang == "en"
    assert set(by_key) == {"picked", "most_recent", "grid"}


def test_parse_still_accepts_a_flat_questions_list():
    _, by_key = _parse_definition({"questions": [{"key": "flat_q", "type": "single"}]})
    assert set(by_key) == {"flat_q"}


def test_parse_tolerates_missing_or_malformed_parts():
    assert _parse_definition(None) == ("en", {})
    assert _parse_definition({"sections": [{"questions": None}, {}]}) == ("en", {})


# ---------------------------------------------------------------------------
# Labels from a sectioned definition
# ---------------------------------------------------------------------------

def test_options_from_resolves_through_sections():
    q = _q("single", "most_recent", options=[("unsure", "Not sure")])
    parsed = _parse_definition(SECTIONED)
    assert _labels(q, {"option": "beta"}, parsed=parsed) == ["Beta option"]
    assert _labels(q, {"option": "unsure"}, parsed=parsed) == ["Not sure"]


def test_matrix_rows_and_points_resolve_through_sections():
    q = _q("matrix", "grid")
    labels = _labels(q, {"ratings": {"row_one": 1, "row_two": 3}}, parsed=_parse_definition(SECTIONED))
    assert labels == ["First row: Low", "Second row: High"]


def test_matrix_not_applicable_resolves_through_sections():
    q = _q("matrix", "grid")
    assert _labels(q, {"ratings": {"row_two": "na"}}, parsed=_parse_definition(SECTIONED)) == [
        "Second row: Does not apply"
    ]


def test_version_def_and_parsed_give_the_same_labels():
    q = _q("matrix", "grid")
    value = {"ratings": {"row_one": 2}}
    assert _labels(q, value, version_def=SECTIONED) == _labels(
        q, value, parsed=_parse_definition(SECTIONED)
    )


# ---------------------------------------------------------------------------
# Through the services, against the database
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def survey_tables(django_db_setup, django_db_blocker):
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


def _sectioned_survey(responses):
    """A survey in PROlog's shape with `responses` submitted responses."""
    survey = Survey.objects.create(id=uuid.uuid4(), slug=f"s-{uuid.uuid4().hex[:8]}", title="Sectioned")
    version = SurveyVersion.objects.create(
        survey=survey, version="1", created_at=timezone.now(), definition=SECTIONED
    )
    picked = SurveyQuestion.objects.create(
        survey_version=version, key="picked", type="multi", order=1, text="Which ones?"
    )
    SurveyOption.objects.create(question=picked, key="alpha", order=1, label="Alpha option", free_text=False)
    SurveyOption.objects.create(question=picked, key="beta", order=2, label="Beta option", free_text=False)
    recent = SurveyQuestion.objects.create(
        survey_version=version, key="most_recent", type="single", order=2, text="Most recent?"
    )
    # The projection holds only the question's own option, as PROlog's does.
    SurveyOption.objects.create(question=recent, key="unsure", order=1, label="Not sure", free_text=False)
    SurveyQuestion.objects.create(survey_version=version, key="grid", type="matrix", order=3, text="Grid")
    for i in range(responses):
        r = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status="submitted")
        SurveyAnswer.objects.create(response=r, question_key="picked", value={"options": ["alpha", "beta"]})
        SurveyAnswer.objects.create(response=r, question_key="most_recent",
                                    value={"option": "beta" if i % 2 else "alpha"})
        SurveyAnswer.objects.create(response=r, question_key="grid",
                                    value={"ratings": {"row_one": 1 + i % 3}})
    return survey


@pytest.mark.django_db
def test_question_responses_labels_sectioned_definition(survey_tables):
    survey = _sectioned_survey(responses=4)
    questions = {q["key"]: q for q in question_responses(survey)["questions"]}
    recent = {o["label"]: o["count"] for o in questions["most_recent"]["options"]}
    assert recent == {"Alpha option": 2, "Beta option": 2}
    grid = {o["label"] for o in questions["grid"]["options"]}
    assert grid == {"First row: Low", "First row: Middle", "First row: High"}


@pytest.mark.django_db
def test_crosstab_labels_sectioned_definition(survey_tables):
    survey = _sectioned_survey(responses=4)
    result = crosstab(survey, "most_recent", "grid")
    assert set(result["x_values"]) == {"Alpha option", "Beta option"}
    assert all(y.startswith("First row: ") for y in result["y_values"])


# ---------------------------------------------------------------------------
# Query shape: what kept a realistic survey within the request timeout
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_catalog_neither_selects_definitions_nor_distincts(survey_tables):
    survey = _sectioned_survey(responses=3)
    with CaptureQueriesContext(connection) as ctx:
        catalog = question_catalog(survey)
    assert {q["key"] for q in catalog} == {"picked", "most_recent", "grid"}
    for query in ctx.captured_queries:
        sql = query["sql"].lower()
        assert "definition" not in sql, sql
        assert "distinct" not in sql, sql


@pytest.mark.django_db
def test_query_count_does_not_grow_with_responses(survey_tables):
    def queries_for(responses):
        survey = _sectioned_survey(responses=responses)
        with CaptureQueriesContext(connection) as ctx:
            question_responses(survey)
            crosstab(survey, "most_recent", "grid")
        return len(ctx.captured_queries)

    assert queries_for(3) == queries_for(30)
