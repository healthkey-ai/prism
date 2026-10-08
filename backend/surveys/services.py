"""Aggregate submitted survey answers without returning respondent data."""
import re
import math
import statistics
from collections import Counter

from django.db.models import Count, Prefetch, Q

from cohorts.views import FL_FIRST_LINE, FL_SECOND_LINE, FL_LATER_LINE
from .models import Survey, SurveyAnswer, SurveyOption, SurveyQuestion, SurveyResponse


CHOICE_TYPES = {"single", "dropdown", "multi", "scale", "matrix", "ranking", "number", "date"}
NUMERIC_TYPES = {"scale", "number"}
ECOG_WORD = re.compile(r"\becog\b", re.I)
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


def _is_numeric(question_type, key, text):
    return question_type in NUMERIC_TYPES or (
        question_type in {"single", "dropdown"} and bool(ECOG_WORD.search(f"{key.replace('_', ' ')} {text}"))
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


def _numeric_value(question, value):
    if not isinstance(value, dict) or value.get("skipped"):
        return None
    if question.type in {"single", "dropdown"} and _is_numeric(question.type, question.key, question.text):
        selected = value.get("option")
        option = next((o for o in question.options.all() if o.key == selected), None)
        if option is None:
            return None
        # ECOG is ordinal 0–5. The demo survey stores digit keys and descriptive
        # labels; other instruments may use opaque keys with a score in the label.
        if re.fullmatch(r"[0-5]", option.key):
            return float(option.key)
        match = re.match(r"^(?:ECOG\s*)?([0-5])\b", option.label, re.I)
        return float(match.group(1)) if match else None
    field = "value" if question.type == "scale" else "number"
    number = value.get(field)
    if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
        return None
    return float(number)


def _summaries(samples):
    return [
        {
            "label": label,
            "n": len(values),
            "mean": statistics.mean(values),
            # Sample SD is undefined for a single response; the chart shows a
            # point without an error bar and reports n=1.
            "sd": statistics.stdev(values) if len(values) > 1 else None,
        }
        for label, values in sorted(samples.items())
    ]


def crosstab(survey, x_key, y_key):
    catalog = {q["key"]: q for q in question_catalog(survey)}
    x_info = catalog.get(x_key, {})
    y_info = catalog.get(y_key, {})
    x_numeric = _is_numeric(x_info.get("type"), x_key, x_info.get("text", ""))
    y_numeric = _is_numeric(y_info.get("type"), y_key, y_info.get("text", ""))
    questions = SurveyQuestion.objects.filter(
        survey_version__survey=survey, key__in=[x_key, y_key]
    ).prefetch_related(Prefetch("options", queryset=SurveyOption.objects.order_by("order")))
    by_version = {(q.survey_version_id, q.key): q for q in questions if eligible(q)}
    counts = Counter()
    x_samples = {}
    y_samples = {}
    paired = 0
    responses = SurveyResponse.objects.filter(
        survey_version__survey=survey, status="submitted"
    ).prefetch_related(Prefetch("answers", queryset=SurveyAnswer.objects.filter(question_key__in=[x_key, y_key])))
    for response in responses.iterator(chunk_size=500):
        answers = {a.question_key: a.value for a in response.answers.all()}
        xq = by_version.get((response.survey_version_id, x_key))
        yq = by_version.get((response.survey_version_id, y_key))
        if not xq or not yq or xq.type != x_info.get("type") or yq.type != y_info.get("type"):
            continue
        x_number = _numeric_value(xq, answers.get(x_key)) if x_numeric else None
        y_number = _numeric_value(yq, answers.get(y_key)) if y_numeric else None
        xs = ["All paired responses"] if x_numeric and x_number is not None else (
            _labels(xq, answers.get(x_key)) if not x_numeric else []
        )
        ys = ["All paired responses"] if y_numeric and y_number is not None else (
            _labels(yq, answers.get(y_key)) if not y_numeric else []
        )
        if xs and ys:
            paired += 1
            if x_numeric:
                for y in ys:
                    x_samples.setdefault(y, []).append(x_number)
            if y_numeric:
                for x in xs:
                    y_samples.setdefault(x, []).append(y_number)
            if not x_numeric and not y_numeric:
                for x in xs:
                    for y in ys:
                        counts[(x, y)] += 1
    if x_numeric or y_numeric:
        numeric_summaries = []
        if x_numeric:
            numeric_summaries.append({"axis": "x", "groups": _summaries(x_samples)})
        if y_numeric:
            numeric_summaries.append({"axis": "y", "groups": _summaries(y_samples)})
        return {"paired_completions": paired, "x_values": [], "y_values": [], "cells": [],
                "numeric_summaries": numeric_summaries}
    x_values = sorted({x for x, _ in counts})
    y_values = sorted({y for _, y in counts})
    return {"paired_completions": paired, "x_values": x_values, "y_values": y_values,
            "cells": [{"x": x, "y": y, "count": counts[(x, y)]} for x in x_values for y in y_values]}
