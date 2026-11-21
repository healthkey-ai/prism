"""Safety and date-consistency checks for the staging demo data operation."""
from datetime import date
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('seed_staging_mm_deaths', Path(__file__).resolve().parents[2] / 'seed_staging_mm_deaths.py')
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)


def row(person_id=1, **changes):
    return {
        'person_id': person_id, 'death_date': None, 'source_death_date': None,
        'has_death_assertion': False, 'first_line_start_date': date(2015, 1, 1),
        'last_treatment': date(2016, 1, 1), 'last_clinical_date': date(2016, 6, 1),
        'first_line_outcome': 'Progressive Disease', 'second_line_outcome': None,
        'later_outcome': None, 'stage': 'R-ISS III', 'markers': 'del17p',
        'patient_age': 70, **changes,
    }


@pytest.mark.parametrize('field,value', [
    ('death_date', date(2020, 1, 1)),
    ('source_death_date', date(2020, 1, 1)),
    ('has_death_assertion', True),
    ('first_line_start_date', None),
    ('last_treatment', None),
    ('last_clinical_date', date(2026, 12, 31)),
])
def test_existing_outcomes_and_ineligible_timelines_are_preserved(field, value):
    assert seed.proposed_death(row(**{field: value}), date(2026, 9, 14)) is None


def test_seed_is_deterministic_and_dates_follow_observations():
    rows = [row(person_id=i) for i in range(100)]
    cutoff = date(2026, 9, 14)
    original = {r['person_id']: seed.proposed_death(r, cutoff) for r in rows}
    reordered = {r['person_id']: seed.proposed_death(r, cutoff) for r in reversed(rows)}
    assert original == reordered
    assert 0 < sum(dd is not None for dd in original.values()) < len(rows)
    for r in rows:
        dd = original[r['person_id']]
        if dd:
            assert r['last_clinical_date'] < dd <= cutoff
            assert seed.proposed_death({**r, 'death_date': dd}, cutoff) is None


def test_same_day_observations_are_consistent_with_death():
    cutoff = date(2026, 9, 14)
    proposed = [seed.proposed_death(row(person_id=i, last_clinical_date=cutoff), cutoff)
                for i in range(100)]
    assert set(proposed) == {None, cutoff}


def test_staging_url_is_required():
    with pytest.raises(ValueError, match='STAGING_DATABASE_URL'):
        seed.staging_url({'DATABASE_URL': 'postgres://prod/db'})


def test_same_database_is_rejected_even_with_render_hostname_alias():
    with pytest.raises(ValueError, match='same database'):
        seed.staging_url({'DATABASE_URL': 'postgres://u:p@dpg-example-a/db',
                          'STAGING_DATABASE_URL': 'postgres://u:p@dpg-example-a.oregon-postgres.render.com/db'})


def test_only_the_staging_url_is_used():
    assert seed.staging_url({'DATABASE_URL': 'postgres://prod/db',
                             'STAGING_DATABASE_URL': 'postgres://staging/db'}) == 'postgres://staging/db'
