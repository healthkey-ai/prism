"""
Incidence over time: diagnoses and treatment initiations per calendar quarter.
"""
from collections import defaultdict


def _quarter(date):
    return f"{date.year} Q{(date.month - 1) // 3 + 1}"


def compute(qs):
    rows = list(qs.values("diagnosis_date", "first_line_start_date"))

    diagnoses: dict = defaultdict(int)
    starts: dict    = defaultdict(int)

    for r in rows:
        if r["diagnosis_date"]:
            diagnoses[_quarter(r["diagnosis_date"])] += 1
        if r["first_line_start_date"]:
            starts[_quarter(r["first_line_start_date"])] += 1

    all_quarters = sorted(set(list(diagnoses) + list(starts)))
    return [
        {
            "quarter":          q,
            "diagnoses":        diagnoses.get(q, 0),
            "treatment_starts": starts.get(q, 0),
        }
        for q in all_quarters
    ]
