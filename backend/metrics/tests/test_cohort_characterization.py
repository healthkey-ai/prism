import pytest
from metrics.services.cohort_characterization import compute, _median_iqr, _pct


def _row(**kwargs):
    defaults = {
        "patient_age": 55, "gender": "F",
        "estrogen_receptor_status": "Positive", "her2_status": "Negative",
        "tnbc_status": False, "stage": "Stage II",
        "ecog_performance_status": 1, "mrd_status": "MRD Negative",
        "hemoglobin_g_dl": 11.5, "serum_creatinine_mg_dl": 0.9,
        "beta2_microglobulin": 2.1,
        "second_line_therapy": None, "later_therapy": None,
    }
    defaults.update(kwargs)
    return defaults


class _FakeQS:
    def __init__(self, rows): self._rows = rows
    def filter(self, *a, **kw): return self
    def exclude(self, *a, **kw): return self
    def values(self, *fields): return [{f: r.get(f) for f in fields} for r in self._rows]
    def values_list(self, *f, flat=False): return [r.get(f[0]) for r in self._rows] if flat else []
    def distinct(self): return self
    def order_by(self, *a): return self


def test_empty_returns_zero():
    assert compute(_FakeQS([])) == {"n": 0}


def test_n_counts_all_rows():
    qs = _FakeQS([_row(), _row(), _row()])
    result = compute(qs)
    assert result["n"] == 3


def test_age_median():
    rows = [_row(patient_age=40), _row(patient_age=50), _row(patient_age=60)]
    result = compute(_FakeQS(rows))
    assert result["demographics"]["age_median"] == 50.0


def test_female_pct():
    rows = [_row(gender="F"), _row(gender="F"), _row(gender="M")]
    result = compute(_FakeQS(rows))
    assert result["demographics"]["female_n"] == 2
    assert result["demographics"]["female_pct"] == pytest.approx(66.7, abs=0.2)


def test_er_positive_pct():
    rows = [_row(estrogen_receptor_status="Positive")] * 3 + \
           [_row(estrogen_receptor_status="Negative")] * 1
    result = compute(_FakeQS(rows))
    assert result["receptor_status"]["er_positive_pct"] == 75.0


def test_treatment_lines():
    rows = [
        _row(second_line_therapy="Drug A", later_therapy="Drug B"),
        _row(second_line_therapy="Drug A", later_therapy=None),
        _row(second_line_therapy=None, later_therapy=None),
    ]
    result = compute(_FakeQS(rows))
    assert result["treatment"]["received_2l_n"] == 2
    assert result["treatment"]["received_3l_n"] == 1


def test_missing_ages_excluded():
    rows = [_row(patient_age=None), _row(patient_age=60)]
    result = compute(_FakeQS(rows))
    assert result["demographics"]["age_median"] == 60.0


def test_median_iqr_odd():
    med, q1, q3 = _median_iqr([1, 2, 3, 4, 5])
    assert med == 3.0


def test_median_iqr_empty():
    assert _median_iqr([]) == (None, None, None)


def test_pct_zero_denom():
    assert _pct(5, 0) is None
