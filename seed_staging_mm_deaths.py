#!/usr/bin/env python3
"""Add deterministic synthetic mortality to Render staging's SYNTHEA-MM cohort.

Dry-run by default. Uses STAGING_DATABASE_URL only. Existing mortality records
and explicit death-date assertions are preserved. OMOP Death, the analytics
mirror and provenance are written atomically. Demo probabilities are illustrative,
not fitted clinical estimates or a target for statistical significance.
"""
import argparse
from datetime import date, timedelta
import json
import os
from pathlib import Path
import random
from urllib.parse import urlparse

from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

SEED_VERSION = 'synthetic-mm-deaths-v1'


def proposed_death(row, cutoff):
    if row['death_date'] or row['source_death_date'] or row['has_death_assertion']:
        return None
    if not row['first_line_start_date'] or not row['last_treatment']:
        return None
    last_observed = max(row['last_treatment'], row['last_clinical_date'], row['first_line_start_date'])
    if last_observed > cutoff:
        return None
    # A per-person stream makes retries and cohort ordering immaterial.
    rng = random.Random(f"{SEED_VERSION}:{row['person_id']}")
    outcome = row['later_outcome'] or row['second_line_outcome'] or row['first_line_outcome'] or ''
    probability = 0.25
    if outcome in ('Progressive Disease', 'Minimal Response'):
        probability += 0.25
    elif outcome == 'Stable Disease':
        probability += 0.10
    if 'III' in (row['stage'] or ''):
        probability += 0.10
    markers = row['markers'] or ''
    if any(marker in markers for marker in ('del(17p)', 'del17p', 't(4;14)', 't(14;16)')):
        probability += 0.10
    if (row['patient_age'] or 0) >= 65:
        probability += 0.05
    if rng.random() >= probability:
        return None
    # Never place clinical care after death. A same-day observation is allowed:
    # this demo cohort has lab snapshots on the cutoff date for every patient.
    available_days = (cutoff - last_observed).days
    max_delay = min(available_days, 365 if outcome == 'Progressive Disease' else 1095)
    delay = rng.randint(1, max_delay) if max_delay else 0
    death = last_observed + timedelta(days=delay)
    return death


def staging_url(environ):
    staging = environ.get('STAGING_DATABASE_URL', '')
    production = environ.get('DATABASE_URL', '')
    if not staging:
        raise ValueError('STAGING_DATABASE_URL is required.')
    def target(url):
        parsed = urlparse(url)
        # Render's internal and external hostnames share the first host label.
        return ((parsed.hostname or '').split('.')[0], parsed.path)
    if production and target(staging) == target(production):
        raise ValueError('Staging and production resolve to the same database target.')
    return staging


def load_cohort(cur):
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='patient_record'")
    columns = {r['column_name'] for r in cur.fetchall()}
    marker = 'cytogenetic_markers' if 'cytogenetic_markers' in columns else 'cytogenic_markers'
    # The fixed organization name AND slug keep all reads/writes on the demo cohort.
    cur.execute(f"""
        WITH cohort AS (
            SELECT p.* FROM patient_record p JOIN organization o ON o.id=p.organization_id
            WHERE o.name='SYNTHEA-MM' AND o.slug='synthea-mm'
              AND lower(p.disease)='multiple myeloma'
        ), clinical_dates AS (
            SELECT d.person_id, greatest(d.drug_exposure_start_date, d.drug_exposure_end_date) AS day
              FROM drug_exposure d JOIN cohort c USING(person_id)
            UNION ALL SELECT d.person_id, greatest(d.condition_start_date, d.condition_end_date)
              FROM condition_occurrence d JOIN cohort c USING(person_id)
            UNION ALL SELECT d.person_id, d.measurement_date
              FROM measurement d JOIN cohort c USING(person_id)
            UNION ALL SELECT d.person_id, d.observation_date
              FROM observation d JOIN cohort c USING(person_id)
            UNION ALL SELECT d.person_id, greatest(d.procedure_date, d.procedure_end_date)
              FROM procedure_occurrence d JOIN cohort c USING(person_id)
            UNION ALL SELECT d.person_id, greatest(d.visit_start_date, d.visit_end_date)
              FROM visit_occurrence d JOIN cohort c USING(person_id)
        ), latest AS (SELECT person_id, max(day) AS day FROM clinical_dates GROUP BY person_id)
        SELECT p.id, p.person_id, p.organization_id, p.death_date, d.death_date AS source_death_date,
               p.first_line_start_date, p.last_treatment, p.stage, p.patient_age,
               p.first_line_outcome, p.second_line_outcome, p.later_outcome,
               p.{marker} AS markers,
               greatest(p.last_treatment, p.first_line_start_date, p.first_line_end_date,
                        p.second_line_start_date, p.second_line_end_date,
                        p.later_start_date, p.later_end_date, l.day) AS last_clinical_date,
               EXISTS(SELECT 1 FROM observation o WHERE o.person_id=p.person_id
                      AND o.observation_source_value='patient-record:death_date') AS has_death_assertion
          FROM cohort p LEFT JOIN death d USING(person_id) LEFT JOIN latest l USING(person_id)
         ORDER BY p.person_id
    """)
    return cur.fetchall()


def apply_plan(cur, plan, cutoff):
    if not plan:
        return
    cur.execute("SELECT id, model FROM django_content_type WHERE app_label='omop_core' AND model IN ('death','patientrecord')")
    content_types = {r['model']: r['id'] for r in cur.fetchall()}
    if set(content_types) != {'death', 'patientrecord'}:
        raise ValueError('Missing source content types for provenance.')
    reason = json.dumps({'purpose': 'User-requested synthetic MM mortality for staging analytics',
                         'seed_version': SEED_VERSION, 'cutoff': cutoff.isoformat(),
                         'synthetic': True, 'previous_death_date': None})
    execute_values(cur, 'INSERT INTO death (person_id,death_date,death_type_concept_id) VALUES %s',
                   [(row['person_id'], death, 0) for row, death in plan], page_size=len(plan))
    execute_values(cur, '''UPDATE patient_record AS p
        SET death_date=v.death_date, updated_at=CURRENT_TIMESTAMP
        FROM (VALUES %s) AS v(id,organization_id,death_date)
        WHERE p.id=v.id AND p.organization_id=v.organization_id AND p.death_date IS NULL''',
        [(row['id'], row['organization_id'], death) for row, death in plan],
        template='(%s,%s,%s::date)', page_size=len(plan))
    if cur.rowcount != len(plan):
        raise ValueError('Cohort changed during the seed; rolling back.')
    provenance = []
    for row, _ in plan:
        for model, object_id in [('death', row['person_id']), ('patientrecord', row['id'])]:
            provenance.append((SEED_VERSION, str(row['person_id']), reason,
                               row['organization_id'], content_types[model], object_id))
    execute_values(cur, '''INSERT INTO provenance_record
        (source,source_user_id,target_patient_id,modification_reason,organization_id,
         created_at,content_type_id,object_id) VALUES %s''', provenance,
        template="('ADMIN_CORRECTION',%s,%s,%s,%s,CURRENT_TIMESTAMP,%s,%s)", page_size=len(provenance))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cutoff', type=date.fromisoformat, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.cutoff > date.today():
        parser.error('Cutoff cannot be in the future.')
    load_dotenv(Path(__file__).resolve().parent / '.env')
    with psycopg2.connect(staging_url(os.environ), connect_timeout=10) as conn:
        conn.set_session(isolation_level='SERIALIZABLE', readonly=not args.apply)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout='60s'")
            if args.apply:
                cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (SEED_VERSION,))
            rows = load_cohort(cur)
            if not rows:
                raise ValueError('No matching synthetic myeloma cohort found.')
            plan = [(row, dd) for row in rows if (dd := proposed_death(row, args.cutoff))]
            summary = {'mode': 'apply' if args.apply else 'dry-run', 'seed_version': SEED_VERSION,
                       'cohort': len(rows), 'existing_deaths': sum(bool(r['death_date']) for r in rows),
                       'new_deaths': len(plan), 'cutoff': str(args.cutoff)}
            if plan:
                summary['death_date_range'] = [str(min(dd for _, dd in plan)), str(max(dd for _, dd in plan))]
                summary['by_stage'] = {stage: sum(r['stage'] == stage for r, _ in plan)
                                       for stage in sorted({r['stage'] for r, _ in plan}, key=lambda s: s or '')}
            if args.apply:
                apply_plan(cur, plan, args.cutoff)
        # The context manager commits all three tables together on successful exit.
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
