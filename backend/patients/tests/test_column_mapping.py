"""Exercise the real ORM against both independently deployed PROMOP schemas."""
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("configured", [None, "cytogenic_markers", "cytogenetic_markers"])
def test_cytogenetics_queries_use_deployed_column(configured):
    env = {
        **os.environ,
        "DJANGO_SETTINGS_MODULE": "analytics_project.test_settings",
        "DATABASE_URL": "",
        "SECRET_KEY": "column-mapping-test",
    }
    env.pop("CYTOGENETIC_MARKERS_DB_COLUMN", None)
    if configured:
        env["CYTOGENETIC_MARKERS_DB_COLUMN"] = configured
    # A fresh process loads the deployment setting before Django builds models.
    result = subprocess.run(
        [sys.executable, "-c", '''
import sys
import django
from django.conf import settings
settings.DATABASES['default']['NAME'] = ':memory:'
django.setup()
from django.db import connection
from django.db.models import Count
from patients.models import PatientInfo
from metrics.services.clinical_filters import HIGH_RISK_CYTO

column = connection.ops.quote_name(sys.argv[1])
with connection.cursor() as cursor:
    cursor.execute(f'CREATE TABLE patient_record (id integer PRIMARY KEY, {column} text)')
    cursor.execute(f'INSERT INTO patient_record VALUES (1, %s), (2, %s)',
                   ['del(17p)', 'hyperdiploidy'])
qs = PatientInfo.objects.all()
assert list(qs.order_by('id').values_list('cytogenic_markers', flat=True)) == [
    'del(17p)', 'hyperdiploidy'
]
assert qs.aggregate(high_risk=Count('id', filter=HIGH_RISK_CYTO)) == {'high_risk': 1}
assert qs.filter(cytogenic_markers__icontains='hyperdiploidy').count() == 1
''', configured or "cytogenic_markers"],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
