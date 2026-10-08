"""Aggregate submitted survey answers without returning respondent data."""
import re
from collections import Counter

from django.db.models import Count, Prefetch, Q

from cohorts.views import FL_FIRST_LINE, FL_SECOND_LINE, FL_LATER_LINE
from .models import Survey, SurveyAnswer, SurveyOption, SurveyQuestion, SurveyResponse


CHOICE_TYPES = {"single", "dropdown", "multi", "scale", "matrix", "ranking", "number", "date"}
TREATMENT_WORDS = re.compile(r"\b(treatments?|therap(?:y|ies)|regimens?|medications?|drugs?)\b", re.I)
THERAPIES = list(dict.fromkeys(FL_FIRST_LINE + FL_SECOND_LINE + FL_LATER_LINE))
ALIASES = {
    "br": FL_FIRST_LINE[0],
    "bendamustine rituximab": FL_FIRST_LINE[0],
    "bendamustine and rituximab": FL_FIRST_LINE[0],
    "rchop": "R-CHOP",
    "gchop": "G-CHOP",
    "rcvp": "R-CVP",
    "r2": "Lenalidomide and Rituximab (R2)",
    "r squared": "Lenalidomide and Rituximab (R2)",
    "lenalidomide rituximab": "Lenalidomide and Rituximab (R2)",
    "axi cel": "Axicabtagene ciloleucel monotherapy",
    "tisa cel": "Tisagenlecleucel monotherapy",
}


def map_fl_treatment(description):
    """Match a named regimen; ambiguous classes and combinations remain unmapped."""
    if not isinstance(description, str):
        return None
    normalized = re.sub(r"[^a-z0-9]+", " ", description.casefold()).strip()
    if not normalized:
        return None
    for therapy in THERAPIES:
        if normalized == re.sub(r"[^a-z0-9]+", " ", therapy.casefold()).strip():
            return therapy
    return ALIASES.get(normalized)


def eligible(question):
    return question.type in CHOICE_TYPES or (
        question.type == "text" and bool(TREATMENT_WORDS.search(question.text))
    )


def survey_catalog():
    surveys = Survey.objects.annotate(
        completions=Count("versions__responses", filter=Q(versions__responses__status="submitted"))
    ).filter(completions__gt=0).order_by("title")
    return [{"id": str(s.pk), "title": s.title, "completions": s.completions} for s in surveys]


def question_catalog(survey):
    # Prefer the most recent question wording; a response is still interpreted
    # using the question and options belonging to its own instrument version.
    questions = SurveyQuestion.objects.filter(
        survey_version__survey=survey,
        survey_version__responses__status="submitted",
    ).select_related("survey_version").order_by("-survey_version__created_at", "order").distinct()
    seen = set()
    result = []
    for question in questions:
        if question.key in seen or not eligible(question):
            continue
        seen.add(question.key)
        result.append({"key": question.key, "text": question.text, "type": question.type})
    return result


def _labels(question, value):
    if not isinstance(value, dict) or value.get("skipped"):
        return []
    option_labels = {o.key: o.label for o in question.options.all()}
    selected = value.get("options") if question.type == "multi" else [value.get("option")]
    if question.type == "scale":
        selected = [value.get("value")]
    if question.type in {"number", "date"}:
        selected = [value.get(question.type)]
    if question.type == "matrix":
        # A matrix has several row values, each a separate categorical answer.
        selected = [f"{row}: {answer}" for row, answer in (value.get("ratings") or {}).items()]
    if question.type == "ranking":
        return [f"{position}: {option_labels.get(key, key)}" for position, key in
                enumerate(value.get("order") or [], start=1)]
    if question.type == "text":
        mapped = map_fl_treatment(value.get("text"))
        return [mapped] if mapped else ["Other / unmapped treatment"] if value.get("text") else []
    labels = [option_labels.get(item, str(item)) for item in selected or [] if item is not None]
    if TREATMENT_WORDS.search(question.text) and value.get("other_text"):
        mapped = map_fl_treatment(value["other_text"])
        labels = [label for label in labels if label != option_labels.get("other")]
        labels.append(mapped or "Other / unmapped treatment")
    return list(dict.fromkeys(labels))


def crosstab(survey, x_key, y_key):
    questions = SurveyQuestion.objects.filter(
        survey_version__survey=survey, key__in=[x_key, y_key]
    ).prefetch_related(Prefetch("options", queryset=SurveyOption.objects.order_by("order")))
    by_version = {(q.survey_version_id, q.key): q for q in questions if eligible(q)}
    counts = Counter()
    paired = 0
    responses = SurveyResponse.objects.filter(
        survey_version__survey=survey, status="submitted"
    ).prefetch_related(Prefetch("answers", queryset=SurveyAnswer.objects.filter(question_key__in=[x_key, y_key])))
    for response in responses.iterator(chunk_size=500):
        answers = {a.question_key: a.value for a in response.answers.all()}
        xq = by_version.get((response.survey_version_id, x_key))
        yq = by_version.get((response.survey_version_id, y_key))
        if not xq or not yq:
            continue
        xs = _labels(xq, answers.get(x_key))
        ys = _labels(yq, answers.get(y_key))
        if xs and ys:
            paired += 1
            for x in xs:
                for y in ys:
                    counts[(x, y)] += 1
    x_values = sorted({x for x, _ in counts})
    y_values = sorted({y for _, y in counts})
    return {"paired_completions": paired, "x_values": x_values, "y_values": y_values,
            "cells": [{"x": x, "y": y, "count": counts[(x, y)]} for x in x_values for y in y_values]}
