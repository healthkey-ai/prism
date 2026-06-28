from datetime import date
from metrics.services.incidence import compute, _quarter


class _FakeQS:
    def __init__(self, rows): self._rows = rows
    def filter(self, *a, **kw): return self
    def exclude(self, *a, **kw): return self
    def values(self, *fields): return [{f: r.get(f) for f in fields} for r in self._rows]
    def distinct(self): return self
    def order_by(self, *a): return self


def _row(diag=None, start=None):
    return {"diagnosis_date": diag, "first_line_start_date": start}


def test_quarter_labelling():
    assert _quarter(date(2022, 1, 15)) == "2022 Q1"
    assert _quarter(date(2022, 4, 1))  == "2022 Q2"
    assert _quarter(date(2022, 7, 31)) == "2022 Q3"
    assert _quarter(date(2022, 10, 1)) == "2022 Q4"


def test_empty_returns_empty():
    assert compute(_FakeQS([])) == []


def test_counts_diagnoses():
    rows = [
        _row(diag=date(2022, 1, 1)),
        _row(diag=date(2022, 2, 1)),
        _row(diag=date(2022, 7, 1)),
    ]
    result = compute(_FakeQS(rows))
    q1 = next(r for r in result if r["quarter"] == "2022 Q1")
    q3 = next(r for r in result if r["quarter"] == "2022 Q3")
    assert q1["diagnoses"] == 2
    assert q3["diagnoses"] == 1


def test_counts_treatment_starts():
    rows = [
        _row(start=date(2022, 3, 1)),
        _row(start=date(2022, 3, 15)),
    ]
    result = compute(_FakeQS(rows))
    assert result[0]["treatment_starts"] == 2


def test_null_dates_skipped():
    rows = [_row(diag=None, start=None)]
    assert compute(_FakeQS(rows)) == []


def test_quarters_sorted():
    rows = [
        _row(diag=date(2023, 1, 1)),
        _row(diag=date(2021, 1, 1)),
        _row(diag=date(2022, 1, 1)),
    ]
    result = compute(_FakeQS(rows))
    quarters = [r["quarter"] for r in result]
    assert quarters == sorted(quarters)
