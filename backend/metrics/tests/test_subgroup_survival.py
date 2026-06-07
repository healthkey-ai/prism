import datetime
import pytest
from unittest.mock import patch, MagicMock
from metrics.services.subgroup_survival import _subgroup_km, compute


D = datetime.date


# ---------------------------------------------------------------------------
# Minimal FakeQS supporting the ORM calls made by os_km / pfs_km / stage split
# ---------------------------------------------------------------------------

class _FakeQS:
    def __init__(self, rows):
        self._rows = list(rows)

    # --- queryset methods used by subgroup splitting ---

    def filter(self, *args, **kwargs):
        return self  # tests control sub-qs directly via monkeypatching

    def exclude(self, *args, **kwargs):
        return self

    def values_list(self, field, flat=False):
        return _FakeValuesList([r.get(field) for r in self._rows])

    # --- queryset methods used by os_km / pfs_km ---

    def values(self, *_fields):
        return self._rows


class _FakeValuesList(list):
    def distinct(self):
        seen = set()
        result = []
        for v in self:
            if v not in seen and v is not None:
                seen.add(v)
                result.append(v)
        return _FakeValuesList(result)

    def order_by(self, *_fields):
        return _FakeValuesList(sorted(self, key=lambda x: (x is None, x)))


def _os_row(start, end=None, death=None, last_tx=None):
    return {
        "first_line_start_date": start,
        "death_date":            death,
        "last_treatment":        last_tx or end,
        "first_line_end_date":   None,
        "first_line_outcome":    None,
        "second_line_end_date":  None,
        "second_line_outcome":   None,
        "later_end_date":        None,
        "later_outcome":         None,
        "second_line_start_date": None,
    }


# ---------------------------------------------------------------------------
# _subgroup_km
# ---------------------------------------------------------------------------

def test_subgroup_km_drops_empty_subgroups():
    from metrics.services.survival import os_km

    populated = _FakeQS([_os_row(D(2020, 1, 1), last_tx=D(2022, 1, 1))])
    empty = _FakeQS([])

    result = _subgroup_km(os_km, [("A", populated), ("B", empty)])

    labels = [r["label"] for r in result]
    assert "A" in labels
    assert "B" not in labels


def test_subgroup_km_attaches_label():
    from metrics.services.survival import os_km

    qs = _FakeQS([_os_row(D(2020, 1, 1), last_tx=D(2022, 1, 1))])
    result = _subgroup_km(os_km, [("My Group", qs)])

    assert result[0]["label"] == "My Group"
    assert "curve" in result[0]
    assert "n" in result[0]
    assert "median" in result[0]


# ---------------------------------------------------------------------------
# compute() — structure checks
# ---------------------------------------------------------------------------

def _make_stage_qs(stages):
    """Build a FakeQS where each row has a 'stage' field and minimal survival fields."""
    rows = []
    for stage in stages:
        row = _os_row(D(2020, 1, 1), last_tx=D(2022, 1, 1))
        row["stage"] = stage
        rows.append(row)
    return _FakeQS(rows)


def test_compute_returns_expected_top_level_keys():
    qs = _make_stage_qs(["ISS Stage I", "ISS Stage II"])
    result = compute(qs)

    assert set(result.keys()) == {"by_stage", "by_cytogenetics", "by_sct"}


def test_compute_each_stratification_has_os_and_pfs():
    qs = _make_stage_qs(["ISS Stage I"])
    result = compute(qs)

    for strat in ("by_stage", "by_cytogenetics", "by_sct"):
        assert "os"  in result[strat], f"{strat} missing 'os'"
        assert "pfs" in result[strat], f"{strat} missing 'pfs'"


def test_compute_subgroup_entries_have_required_fields():
    qs = _make_stage_qs(["ISS Stage I", "ISS Stage II"])
    result = compute(qs)

    for entry in result["by_stage"]["os"]:
        assert "label"  in entry
        assert "n"      in entry
        assert "curve"  in entry
        assert "median" in entry
