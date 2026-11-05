"""Scale questions tabulated in the grid, ISO 3166 country names, and question numbers (#94)."""
import uuid

import pytest
from django.utils import timezone

from surveys.models import Survey, SurveyAnswer, SurveyOption, SurveyQuestion, SurveyResponse, SurveyVersion
from surveys.services import (
    _country_names, country_name, crosstab, question_catalog, question_number, question_responses, response_export,
)
from surveys.tests.test_survey_responses import survey_tables  # noqa: F401  (module fixture)


INFORMED_SCALE = {
    "min": 1, "max": 5,
    "min_label": {"en": "Not informed at all", "es": "Nada informado(a)"},
    "max_label": {"en": "Very well informed", "es": "Muy bien informado(a)"},
}


def _definition():
    return {
        "default_language": "en",
        "sections": [{
            "key": "s1",
            "questions": [
                {"key": "q1_country", "type": "dropdown", "config": {"options_source": "iso3166_countries"}},
                {"key": "q11_cart_informed", "type": "scale", "config": {"scale": INFORMED_SCALE}},
                {"key": "q13_info_needs", "type": "multi",
                 "options": [{"key": "risks", "label": {"en": "Risks and side effects"}}]},
            ],
        }],
    }


def _survey(slug, definition=None):
    survey = Survey.objects.create(id=uuid.uuid4(), slug=slug, title=slug)
    version = SurveyVersion.objects.create(
        survey=survey, version="1", created_at=timezone.now(), definition=definition,
    )
    return survey, version


def _respond(version, **answers):
    response = SurveyResponse.objects.create(id=uuid.uuid4(), survey_version=version, status="submitted")
    for key, value in answers.items():
        SurveyAnswer.objects.create(response=response, question_key=key, value=value)
    return response


@pytest.mark.parametrize("key, expected", [
    ("q1_country", "1"),
    ("q7a_recent_treatment", "7a"),
    ("q16b_involvement_preferred", "16b"),
    ("Q10B_treatment_change", "10b"),
    ("country", None),
    ("quality_of_life", None),
    ("", None),
    (None, None),
])
def test_question_number_from_key(key, expected):
    assert question_number(key) == expected


def test_country_name_resolves_alpha_2_codes():
    assert country_name("GB") == "United Kingdom"
    assert country_name("us") == "United States"
    assert country_name("ZZ") is None
    assert country_name(None) is None


@pytest.mark.django_db
def test_scale_question_is_tabulated_with_end_point_labels(survey_tables):  # noqa: F811
    survey, version = _survey("scale-grid", _definition())
    SurveyQuestion.objects.create(
        survey_version=version, key="q11_cart_informed", type="scale", order=1,
        text="How well informed do you feel about CAR-T therapy?",
    )
    for point in (1, 1, 3, 5):
        _respond(version, q11_cart_informed={"value": point})
    _respond(version, q11_cart_informed={"skipped": True})

    result = question_responses(survey)
    assert len(result["questions"]) == 1
    q = result["questions"][0]
    assert q["number"] == "11"
    assert q["n"] == 4
    # Points read in scale order, labelled from the definition's end points.
    assert q["options"] == [
        {"label": "1 – Not informed at all", "count": 2, "pct": 50.0},
        {"label": "3", "count": 1, "pct": 25.0},
        {"label": "5 – Very well informed", "count": 1, "pct": 25.0},
    ]
    assert q["zero_options"] == ["2", "4"]


@pytest.mark.django_db
def test_scale_export_and_catalog_carry_number(survey_tables):  # noqa: F811
    survey, version = _survey("scale-export", _definition())
    SurveyQuestion.objects.create(
        survey_version=version, key="q11_cart_informed", type="scale", order=1, text="CAR-T informed?",
    )
    r = _respond(version, q11_cart_informed={"value": 5.0})

    export = response_export(survey)
    assert export["questions"] == [{"key": "q11_cart_informed", "number": "11", "text": "CAR-T informed?"}]
    assert export["rows"][0]["respondent_id"] == str(r.id)
    assert export["rows"][0]["answers"]["q11_cart_informed"] == "5 – Very well informed"

    catalog = question_catalog(survey)
    assert catalog[0]["number"] == "11"
    assert catalog[0]["type"] == "scale"


@pytest.mark.django_db
def test_scale_stays_numeric_in_crosstab(survey_tables):  # noqa: F811
    survey, version = _survey("scale-crosstab", _definition())
    SurveyQuestion.objects.create(
        survey_version=version, key="q11_cart_informed", type="scale", order=1, text="CAR-T informed?",
    )
    q = SurveyQuestion.objects.create(
        survey_version=version, key="q13_info_needs", type="multi", order=2, text="Info needs",
    )
    SurveyOption.objects.create(question=q, key="risks", order=0, label="Risks and side effects", free_text=False)
    _respond(version, q11_cart_informed={"value": 2}, q13_info_needs={"options": ["risks"]})
    _respond(version, q11_cart_informed={"value": 4}, q13_info_needs={"options": ["risks"]})

    result = crosstab(survey, "q11_cart_informed", "q13_info_needs")
    assert result["paired_completions"] == 2
    assert result["numeric_summaries"] == [
        {"axis": "x", "groups": [{"label": "Risks and side effects", "n": 2, "mean": 3.0, "sd": pytest.approx(1.4142, abs=1e-3)}]},
    ]


@pytest.mark.django_db
def test_iso3166_country_codes_get_names_on_hover_and_a_zero_list(survey_tables):  # noqa: F811
    survey, version = _survey("country-grid", _definition())
    SurveyQuestion.objects.create(
        survey_version=version, key="q1_country", type="dropdown", order=1, text="Which country do you live in?",
    )
    # PROlog materialises no SurveyOption rows for a built-in option source.
    for code in ("GB", "GB", "US"):
        _respond(version, q1_country={"option": code})

    result = question_responses(survey)
    q = result["questions"][0]
    assert q["number"] == "1"
    assert q["options"] == [
        {"label": "GB", "count": 2, "pct": 66.7, "title": "United Kingdom"},
        {"label": "US", "count": 1, "pct": 33.3, "title": "United States"},
    ]
    assert "United Kingdom" not in q["zero_options"]
    assert "United States" not in q["zero_options"]
    assert "France" in q["zero_options"]
    assert q["zero_options"] == sorted(q["zero_options"])
    assert len(q["zero_options"]) == len(_country_names()) - 2


@pytest.mark.django_db
def test_iso3166_options_source_include_limits_the_zero_list(survey_tables):  # noqa: F811
    definition = _definition()
    definition["sections"][0]["questions"][0]["config"]["options_source_include"] = ["GB", "FR", "DE"]
    survey, version = _survey("country-include", definition)
    SurveyQuestion.objects.create(
        survey_version=version, key="q1_country", type="dropdown", order=1, text="Country",
    )
    _respond(version, q1_country={"option": "GB"})

    q = question_responses(survey)["questions"][0]
    assert q["options"] == [{"label": "GB", "count": 1, "pct": 100.0, "title": "United Kingdom"}]
    assert q["zero_options"] == ["France", "Germany"]


@pytest.mark.django_db
def test_country_export_and_crosstab_use_full_names(survey_tables):  # noqa: F811
    survey, version = _survey("country-export", _definition())
    SurveyQuestion.objects.create(
        survey_version=version, key="q1_country", type="dropdown", order=1, text="Country",
    )
    q = SurveyQuestion.objects.create(
        survey_version=version, key="q13_info_needs", type="multi", order=2, text="Info needs",
    )
    SurveyOption.objects.create(question=q, key="risks", order=0, label="Risks and side effects", free_text=False)
    _respond(version, q1_country={"option": "GB"}, q13_info_needs={"options": ["risks"]})

    export = response_export(survey)
    assert export["rows"][0]["answers"]["q1_country"] == "United Kingdom"

    table = crosstab(survey, "q1_country", "q13_info_needs")
    assert table["x_values"] == ["GB"]
    assert table["x_titles"] == {"GB": "United Kingdom"}
    assert table["y_titles"] == {}


@pytest.mark.django_db
def test_inline_dropdown_options_are_unaffected(survey_tables):  # noqa: F811
    survey, version = _survey("country-inline")
    q = SurveyQuestion.objects.create(
        survey_version=version, key="country", type="single", order=1, text="Country",
    )
    SurveyOption.objects.create(question=q, key="gb", order=0, label="United Kingdom", free_text=False)
    _respond(version, country={"option": "gb"})

    result = question_responses(survey)["questions"][0]
    assert result["options"] == [{"label": "United Kingdom", "count": 1, "pct": 100.0}]
    assert result["zero_options"] == []
