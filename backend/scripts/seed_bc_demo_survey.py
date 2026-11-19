#!/usr/bin/env python
"""Seed a synthetic breast-cancer demo survey on a staging database.

Creates the "BC treatment and outcomes demo" survey (slug
``prism-bc-crosstab-demo``) in PROlog's tables with one submitted response per
sampled SYNTHEA-BC patient. Each response's ``participant_id`` is the patient's
PROMOP person, so PRism's cohort scoping places the answers in that org, and the
answers themselves are derived from the patient's record (first-line therapy and
outcome, stage, ECOG); time since treatment is drawn at random, as in the FL
demo, because Synthea treatment dates all lie years in the past. It mirrors the FL demo survey
(``prism-fl-crosstab-demo``), whose version row is used as the template for the
PROlog bookkeeping columns.

Usage (from backend/):

    python scripts/seed_bc_demo_survey.py --database-url "$STAGING_DATABASE_URL"
    python scripts/seed_bc_demo_survey.py --database-url ... --replace   # rebuild

Only ever point this at a staging database: it writes to PROMOP-owned tables.
"""
import argparse
import hashlib
import json
import os
import random
import sys
import uuid
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

SLUG = "prism-bc-crosstab-demo"
TITLE = "BC treatment and outcomes demo (synthetic staging data)"
TEMPLATE_SLUG = "prism-fl-crosstab-demo"
ORG = "SYNTHEA-BC"

# patient_record.first_line_therapy -> option key
TREATMENTS = [
    ("ac_t", "AC-T (Doxorubicin, Cyclophosphamide, then Paclitaxel)", {"AC-T"}),
    ("tc", "Docetaxel and Cyclophosphamide (TC)", {"Cyclophosphamide and Docetaxel (TC)"}),
    ("thp", "THP (Taxane, Trastuzumab, Pertuzumab)", {"THP (Paclitaxel)", "THP (Docetaxel)"}),
    ("tamoxifen", "Tamoxifen monotherapy", {"Tamoxifen monotherapy"}),
    ("mc", "Cyclophosphamide and liposomal doxorubicin (MC)",
     {"Cyclophosphamide and Non-pegylated liposomal doxorubicin (MC)"}),
    ("t_dxd", "Trastuzumab deruxtecan (Enhertu) monotherapy", {"Trastuzumab deruxtecan monotherapy"}),
    ("palbo_ai", "Palbociclib + aromatase inhibitor", {"Palbociclib+AI"}),
]
TREATMENT_KEY = {name: key for key, _, names in TREATMENTS for name in names}

OUTCOMES = [
    ("cr", "Complete Response (CR)"),
    ("pr", "Partial Response (PR)"),
    ("sd", "Stable Disease (SD)"),
    ("pd", "Progressive Disease (PD)"),
]
OUTCOME_KEY = {
    "Complete Response": "cr", "Partial Response": "pr",
    "Stable Disease": "sd", "Progressive Disease": "pd",
}

ECOG = [
    ("0", "0 - Fully active"),
    ("1", "1 - Restricted in physically strenuous activity"),
    ("2", "2 - Ambulatory and capable of self-care"),
    ("3", "3 - Capable of only limited self-care"),
    ("4", "4 - Completely disabled"),
]

# NCIt codes, as the FL demo uses them.
STAGES = [
    ("c27966", "Stage I"), ("c28054", "Stage II"), ("c27970", "Stage III"), ("c27971", "Stage IV"),
]
STAGE_KEY = {
    "I": "c27966", "1": "c27966", "II": "c28054", "2": "c28054",
    "III": "c27970", "3": "c27970", "IV": "c27971", "4": "c27971",
}

TIME_SINCE = [
    ("under_6_months", "Less than 6 months"),
    ("six_to_12_months", "6 to 12 months"),
    ("one_to_two_years", "1 to 2 years"),
    ("over_two_years", "More than 2 years"),
]

QUESTIONS = [
    ("last_treatment", "What was your last breast cancer treatment?", [(k, l) for k, l, _ in TREATMENTS]),
    ("outcome", "What was the outcome of that treatment?", OUTCOMES),
    ("ecog", "What is your current ECOG performance score?", ECOG),
    ("stage", "What is the stage of your disease?", STAGES),
    ("time_since_treatment", "How long has it been since your last treatment?", TIME_SINCE),
]


def stage_key(stage):
    """'Stage IIA' / 'Stage 3 (qualifier value)' -> option key, else None."""
    if not stage:
        return None
    token = stage.replace("Stage", "").strip().split(" ")[0]
    token = token.rstrip("ABC")
    return STAGE_KEY.get(token)


def definition():
    return {
        "slug": SLUG,
        "title": {"en": TITLE},
        "intro": {"en": "Demonstration survey for synthetic breast cancer patient records."},
        "notes": "Synthetic staging fixture for PRism crosstab demonstrations; values derived from SYNTHEA-BC patient records.",
        "status": "draft",
        "version": "1.0",
        "sections": [{
            "key": "treatment_outcomes",
            "title": {"en": "Treatment and disease status"},
            "questions": [{
                "key": key,
                "text": {"en": text},
                "type": "single",
                "config": {},
                "required": True,
                "visible_if": [],
                "options": [
                    {"key": ok, "label": {"en": ol}, "exclusive": False, "free_text": False}
                    for ok, ol in options
                ],
            } for key, text, options in QUESTIONS],
        }],
    }


def delete_survey(cur, slug):
    cur.execute("SELECT id FROM prolog_surveys_survey WHERE slug = %s", (slug,))
    row = cur.fetchone()
    if not row:
        return False
    survey_id = row[0]
    cur.execute("""
        DELETE FROM prolog_surveys_surveyanswer WHERE response_id IN (
            SELECT r.id FROM prolog_surveys_surveyresponse r
            JOIN prolog_surveys_surveyversion v ON v.id = r.survey_version_id
            WHERE v.survey_id = %s)""", (survey_id,))
    cur.execute("""
        DELETE FROM prolog_surveys_surveyresponse WHERE survey_version_id IN (
            SELECT id FROM prolog_surveys_surveyversion WHERE survey_id = %s)""", (survey_id,))
    cur.execute("""
        DELETE FROM prolog_surveys_surveyoption WHERE question_id IN (
            SELECT q.id FROM prolog_surveys_surveyquestion q
            JOIN prolog_surveys_surveyversion v ON v.id = q.survey_version_id
            WHERE v.survey_id = %s)""", (survey_id,))
    cur.execute("""
        DELETE FROM prolog_surveys_surveyquestion WHERE survey_version_id IN (
            SELECT id FROM prolog_surveys_surveyversion WHERE survey_id = %s)""", (survey_id,))
    cur.execute("DELETE FROM prolog_surveys_surveyversion WHERE survey_id = %s", (survey_id,))
    cur.execute("DELETE FROM prolog_surveys_survey WHERE id = %s", (survey_id,))
    return True


def sample_patients(cur, org, count, rng):
    cur.execute("""
        SELECT pr.person_id, pr.first_line_therapy, pr.first_line_outcome, pr.stage,
               pr.ecog_performance_status
        FROM patient_record pr
        JOIN organization o ON o.id = pr.organization_id
        WHERE o.name = %s AND pr.person_id IS NOT NULL
          AND pr.first_line_therapy IS NOT NULL AND pr.first_line_outcome IS NOT NULL
        ORDER BY pr.person_id""", (org,))
    eligible = [
        r for r in cur.fetchall()
        if r[1] in TREATMENT_KEY and r[2] in OUTCOME_KEY
    ]
    if len(eligible) < count:
        sys.exit(f"Only {len(eligible)} {org} patients have a mappable first-line therapy and outcome; need {count}.")
    return rng.sample(eligible, count)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database-url", default=os.environ.get("STAGING_DATABASE_URL"))
    parser.add_argument("--org", default=ORG)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20261111)
    parser.add_argument("--replace", action="store_true", help="Delete an existing demo survey first.")
    args = parser.parse_args()
    if not args.database_url:
        sys.exit("Pass --database-url or set STAGING_DATABASE_URL.")

    rng = random.Random(args.seed)
    now = datetime.now(timezone.utc)

    conn = psycopg2.connect(args.database_url)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT 1 FROM prolog_surveys_survey WHERE slug = %s", (SLUG,))
            if cur.fetchone():
                if not args.replace:
                    sys.exit(f"Survey {SLUG} already exists; pass --replace to rebuild it.")
                delete_survey(cur, SLUG)

            cur.execute("""
                SELECT s.theme_code, s.allow_anonymous_participation, v.status, v.schema_version, v.source
                FROM prolog_surveys_survey s
                JOIN prolog_surveys_surveyversion v ON v.survey_id = s.id
                WHERE s.slug = %s ORDER BY v.created_at DESC LIMIT 1""", (TEMPLATE_SLUG,))
            template = cur.fetchone()
            if not template:
                sys.exit(f"Template survey {TEMPLATE_SLUG} not found; nothing to copy PROlog bookkeeping from.")
            theme_code, allow_anonymous, v_status, schema_version, source = template

            patients = sample_patients(cur, args.org, args.count, rng)

            survey_id = uuid.uuid4()
            cur.execute("""
                INSERT INTO prolog_surveys_survey
                    (id, slug, title, theme_code, allow_anonymous_participation, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (str(survey_id), SLUG, TITLE, theme_code, allow_anonymous, now, now))

            defn = definition()
            defn_json = json.dumps(defn, sort_keys=True)
            checksum = hashlib.sha256(defn_json.encode()).hexdigest()
            cur.execute("""
                INSERT INTO prolog_surveys_surveyversion
                    (version, status, schema_version, definition, checksum, source,
                     created_at, updated_at, survey_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                ("1.0", v_status, schema_version, psycopg2.extras.Json(defn), checksum, source, now, now, str(survey_id)))
            version_id = cur.fetchone()[0]

            for order, (key, text, options) in enumerate(QUESTIONS):
                cur.execute("""
                    INSERT INTO prolog_surveys_surveyquestion
                        (key, section_key, type, "order", text, required, survey_version_id)
                    VALUES (%s, 'treatment_outcomes', 'single', %s, %s, true, %s) RETURNING id""",
                    (key, order, text, version_id))
                question_id = cur.fetchone()[0]
                for o_order, (ok, ol) in enumerate(options):
                    cur.execute("""
                        INSERT INTO prolog_surveys_surveyoption
                            (key, "order", label, exclusive, free_text, question_id)
                        VALUES (%s, %s, %s, false, false, %s)""", (ok, o_order, ol, question_id))

            last_key = QUESTIONS[-1][0]
            for person_id, therapy, outcome, stage, ecog in patients:
                answers = {
                    "last_treatment": TREATMENT_KEY[therapy],
                    "outcome": OUTCOME_KEY[outcome],
                    "ecog": str(ecog) if ecog is not None else rng.choice(["0", "1", "1", "2"]),
                    "stage": stage_key(stage) or rng.choice([k for k, _ in STAGES]),
                    "time_since_treatment": rng.choice([k for k, _ in TIME_SINCE]),
                }
                response_id = uuid.uuid4()
                cur.execute("""
                    INSERT INTO prolog_surveys_surveyresponse
                        (id, language, status, started_at, updated_at, submitted_at, last_question_key,
                         user_agent_hash, survey_version_id, participant_id)
                    VALUES (%s, 'en', 'submitted', %s, %s, %s, %s, '', %s, %s)""",
                    (str(response_id), now, now, now, last_key, version_id, person_id))
                for key, option in answers.items():
                    cur.execute("""
                        INSERT INTO prolog_surveys_surveyanswer
                            (question_key, value, option_keys, created_at, updated_at, response_id)
                        VALUES (%s, %s, %s, %s, %s, %s)""",
                        (key, psycopg2.extras.Json({"option": option}), psycopg2.extras.Json([option]),
                         now, now, str(response_id)))

        print(f"Seeded {len(patients)} submitted responses to '{TITLE}' for {args.org} patients.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
