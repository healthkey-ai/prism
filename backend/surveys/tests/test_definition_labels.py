"""Tests for label resolution via the version definition (issue #70).

Covers the three question kinds whose labels live in the definition rather than
the SurveyOption projection:
  1. single / dropdown with config.options_from
  2. matrix with fixed config.rows and a point scale
  3. matrix answered "na"
  4. matrix with config.rows_from
  5. definition absent or question key missing → falls back to key / raw value
  6. two versions with different labels → each response uses its own version
"""
import uuid
from types import SimpleNamespace

import pytest
from django.db import connection
from django.utils import timezone

from surveys.models import (
    Survey,
    SurveyAnswer,
    SurveyOption,
    SurveyQuestion,
    SurveyResponse,
    SurveyVersion,
)
from surveys.services import _labels, question_responses


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _q(type_, key, options=(), version_def=None):
    """Build a SimpleNamespace question for _labels unit tests."""
    return SimpleNamespace(
        type=type_,
        key=key,
        text=key,
        options=SimpleNamespace(all=lambda opts=list(options): [
            SimpleNamespace(key=k, label=l) for k, l in opts
        ]),
    )


# ---------------------------------------------------------------------------
# 1. options_from single
# ---------------------------------------------------------------------------

_OPTIONS_FROM_DEF = {
    "default_language": "en",
    "questions": [
        {
            "key": "source_q",
            "type": "multi",
            "config": {},
            "options": [
                {"key": "src1", "label": {"en": "Source Option One"}},
                {"key": "src2", "label": {"en": "Source Option Two"}},
            ],
        },
        {
            "key": "derived_q",
            "type": "single",
            "config": {"options_from": "source_q"},
            "options": [{"key": "not_sure", "label": {"en": "Not sure"}}],
        },
    ],
}


def test_options_from_single_sourced_option():
    """Answer whose key comes from the source question is resolved to the source label."""
    q = _q("single", "derived_q", options=[("not_sure", "Not sure")])
    assert _labels(q, {"option": "src1"}, version_def=_OPTIONS_FROM_DEF) == ["Source Option One"]


def test_options_from_single_own_option():
    """The question's own options (e.g. 'Not sure') are also resolved correctly."""
    q = _q("single", "derived_q", options=[("not_sure", "Not sure")])
    assert _labels(q, {"option": "not_sure"}, version_def=_OPTIONS_FROM_DEF) == ["Not sure"]


# ---------------------------------------------------------------------------
# 2. Matrix with fixed rows + point_labels scale
# ---------------------------------------------------------------------------

_MATRIX_SCALE_DEF = {
    "default_language": "en",
    "questions": [
        {
            "key": "q_matrix",
            "type": "matrix",
            "config": {
                "rows": [
                    {"key": "row1", "label": {"en": "Fatigue level"}},
                    {"key": "row2", "label": {"en": "Pain level"}},
                ],
                "scale": {
                    "min": 1,
                    "max": 3,
                    "point_labels": [
                        {"en": "Low"},
                        {"en": "Medium"},
                        {"en": "High"},
                    ],
                    "not_applicable": {"en": "Not applicable"},
                },
            },
        }
    ],
}


def test_matrix_row_and_scale_point_labels():
    """Row keys and integer scale points are resolved to definition labels."""
    q = _q("matrix", "q_matrix")
    result = _labels(q, {"ratings": {"row1": 1, "row2": 3}}, version_def=_MATRIX_SCALE_DEF)
    assert result == ["Fatigue level: Low", "Pain level: High"]


def test_matrix_middle_point_label():
    q = _q("matrix", "q_matrix")
    result = _labels(q, {"ratings": {"row1": 2}}, version_def=_MATRIX_SCALE_DEF)
    assert result == ["Fatigue level: Medium"]


# ---------------------------------------------------------------------------
# 3. Matrix answered "na"
# ---------------------------------------------------------------------------

def test_matrix_na_answer_uses_not_applicable_label():
    q = _q("matrix", "q_matrix")
    result = _labels(q, {"ratings": {"row1": "na"}}, version_def=_MATRIX_SCALE_DEF)
    assert result == ["Fatigue level: Not applicable"]


# ---------------------------------------------------------------------------
# 4. rows_from matrix
# ---------------------------------------------------------------------------

_ROWS_FROM_DEF = {
    "default_language": "en",
    "questions": [
        {
            "key": "selection_q",
            "type": "multi",
            "config": {},
            "options": [
                {"key": "sym1", "label": {"en": "Nausea"}},
                {"key": "sym2", "label": {"en": "Headache"}},
            ],
        },
        {
            "key": "rate_q",
            "type": "matrix",
            "config": {
                "rows_from": "selection_q",
                "scale": {
                    "min": 1,
                    "max": 2,
                    "point_labels": [{"en": "Mild"}, {"en": "Severe"}],
                    "not_applicable": {"en": "N/A"},
                },
            },
        },
    ],
}


def test_rows_from_matrix():
    """Row keys sourced from an earlier question's options are resolved via rows_from."""
    q = _q("matrix", "rate_q")
    result = _labels(q, {"ratings": {"sym1": 2, "sym2": 1}}, version_def=_ROWS_FROM_DEF)
    assert set(result) == {"Nausea: Severe", "Headache: Mild"}


# ---------------------------------------------------------------------------
# 5. No definition → falls back to raw keys / numbers
# ---------------------------------------------------------------------------

def test_no_definition_falls_back_to_projection_keys():
    """Without a version definition the existing projection-based fallback is used."""
    q = _q("single", "q", options=[("opt1", "Projected Label")])
    # Key in projection → resolved.
    assert _labels(q, {"option": "opt1"}) == ["Projected Label"]
    # Key absent from projection → raw key shown.
    assert _labels(q, {"option": "unknown_key"}) == ["unknown_key"]


def test_no_definition_matrix_falls_back_to_raw():
    q = _q("matrix", "q_matrix")
    result = _labels(q, {"ratings": {"row1": 3}})
    assert result == ["row1: 3"]


def test_definition_missing_question_key_falls_back():
    """If the definition exists but doesn't mention this question, fall back gracefully."""
    definition = {"default_language": "en", "questions": []}
    q = _q("single", "derived_q", options=[("k", "Projection Label")])
    assert _labels(q, {"option": "k"}, version_def=definition) == ["Projection Label"]


# ---------------------------------------------------------------------------
# 6. Two versions with different labels — each response uses its own version
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def survey_tables_def(django_db_setup, django_db_blocker):
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


_DEF_V1 = {
    "default_language": "en",
    "questions": [
        {
            "key": "source_q",
            "type": "multi",
            "config": {},
            "options": [{"key": "opt_a", "label": {"en": "Version 1 label"}}],
        },
        {
            "key": "derived_q",
            "type": "single",
            "config": {"options_from": "source_q"},
            "options": [],
        },
    ],
}

_DEF_V2 = {
    "default_language": "en",
    "questions": [
        {
            "key": "source_q",
            "type": "multi",
            "config": {},
            "options": [{"key": "opt_a", "label": {"en": "Version 2 label"}}],
        },
        {
            "key": "derived_q",
            "type": "single",
            "config": {"options_from": "source_q"},
            "options": [],
        },
    ],
}


@pytest.mark.django_db
def test_two_versions_use_their_own_definition(survey_tables_def):
    """Responses from different versions show each version's own label wording."""
    survey = Survey.objects.create(id=uuid.uuid4(), slug="two-ver", title="Two versions")
    v1 = SurveyVersion.objects.create(
        survey=survey, version="1", created_at=timezone.now(), definition=_DEF_V1
    )
    v2 = SurveyVersion.objects.create(
        survey=survey, version="2", created_at=timezone.now(), definition=_DEF_V2
    )
    # Projection option missing for the sourced key → requires definition to resolve.
    q1 = SurveyQuestion.objects.create(
        survey_version=v1, key="derived_q", type="single", order=1, text="Which?"
    )
    q2 = SurveyQuestion.objects.create(
        survey_version=v2, key="derived_q", type="single", order=1, text="Which?"
    )

    r1 = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=v1, status="submitted")
    SurveyAnswer.objects.create(response=r1, question_key="derived_q", value={"option": "opt_a"})

    r2 = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=v2, status="submitted")
    SurveyAnswer.objects.create(response=r2, question_key="derived_q", value={"option": "opt_a"})

    result = question_responses(survey)
    questions = {q["key"]: q for q in result["questions"]}
    derived = questions["derived_q"]
    option_map = {o["label"]: o["count"] for o in derived["options"]}
    # Each version contributes one response with its own label wording.
    assert option_map.get("Version 1 label", 0) == 1
    assert option_map.get("Version 2 label", 0) == 1
