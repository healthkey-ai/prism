from datetime import date, timedelta
from metrics.services.time_to_treatment import compute


class _FakeQS:
    def __init__(self, rows): self._rows = rows
    def filter(self, *a, **kw): return self
    def exclude(self, *a, **kw): return self
    def values(self, *fields): return [{f: r.get(f) for f in fields} for r in self._rows]
    def distinct(self): return self
    def order_by(self, *a): return self


def _row(diag_offset, start_offset):
    base = date(2020, 1, 1)
    return {
        "diagnosis_date":       base + timedelta(days=diag_offset),
        "first_line_start_date": base + timedelta(days=start_offset),
    }


def test_empty_returns_none_median():
    result = compute(_FakeQS([]))
    assert result["median_days"] is None
    assert result["n"] == 0


def test_median_single_patient():
    result = compute(_FakeQS([_row(0, 45)]))
    assert result["median_days"] == 45
    assert result["n"] == 1


def test_median_multiple():
    rows = [_row(0, 10), _row(0, 50), _row(0, 90)]
    result = compute(_FakeQS(rows))
    assert result["median_days"] == 50


def test_histogram_bins():
    rows = [
        _row(0, 15),   # 0–30d
        _row(0, 45),   # 30–60d
        _row(0, 400),  # 365d+
    ]
    result = compute(_FakeQS(rows))
    hist = {h["label"]: h["count"] for h in result["histogram"]}
    assert hist["0–30d"]  == 1
    assert hist["30–60d"] == 1
    assert hist["365d+"]  == 1


def test_negative_days_excluded():
    rows = [{"diagnosis_date": date(2020, 6, 1), "first_line_start_date": date(2020, 1, 1)}]
    result = compute(_FakeQS(rows))
    assert result["n"] == 0


def test_null_dates_excluded():
    rows = [{"diagnosis_date": None, "first_line_start_date": date(2020, 6, 1)}]
    result = compute(_FakeQS(rows))
    assert result["n"] == 0


def test_histogram_all_bins_present():
    result = compute(_FakeQS([_row(0, 30)]))
    assert len(result["histogram"]) == 6
