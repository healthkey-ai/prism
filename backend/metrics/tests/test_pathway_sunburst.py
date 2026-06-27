import pytest
from metrics.services.pathway_sunburst import compute, _short


class _FakeQS:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def exclude(self, *args, **kwargs):
        return self

    def values(self, *_fields):
        return list(self._rows)


def qs(rows):
    return _FakeQS(rows)


# ---------------------------------------------------------------------------
# _short helper
# ---------------------------------------------------------------------------

def test_short_truncates_at_paren():
    assert _short("VRd (Bortezomib-Lenalidomide-Dex)") == "VRd"


def test_short_clips_long_name():
    name = "A" * 40
    assert _short(name) == "A" * 30


def test_short_returns_none_for_empty():
    assert _short(None) is None
    assert _short("") is None


# ---------------------------------------------------------------------------
# compute
# ---------------------------------------------------------------------------

def test_empty():
    result = compute(qs([]))
    assert result["total"] == 0
    assert result["children"] == []


def test_basic_tree():
    rows = [
        {"first_line_therapy": "VRd", "second_line_therapy": "DPd", "later_therapy": None},
        {"first_line_therapy": "VRd", "second_line_therapy": "DPd", "later_therapy": None},
        {"first_line_therapy": "VRd", "second_line_therapy": None,  "later_therapy": None},
        {"first_line_therapy": "DRd", "second_line_therapy": "Pom", "later_therapy": None},
    ]
    result = compute(qs(rows))
    assert result["total"] == 4

    names = [c["name"] for c in result["children"]]
    assert names[0] == "VRd"   # larger count first
    assert names[1] == "DRd"

    vrd = result["children"][0]
    assert vrd["count"] == 3
    assert len(vrd["children"]) == 1
    assert vrd["children"][0]["name"] == "DPd"
    assert vrd["children"][0]["count"] == 2


def test_three_levels():
    rows = [
        {"first_line_therapy": "VRd", "second_line_therapy": "DPd", "later_therapy": "Car-T"},
        {"first_line_therapy": "VRd", "second_line_therapy": "DPd", "later_therapy": "Car-T"},
        {"first_line_therapy": "VRd", "second_line_therapy": "DPd", "later_therapy": "Pom"},
    ]
    result = compute(qs(rows))
    assert result["total"] == 3

    vrd = result["children"][0]
    dpd = vrd["children"][0]
    assert dpd["name"] == "DPd"
    assert dpd["count"] == 3

    third_names = [c["name"] for c in dpd["children"]]
    assert "Car-T" in third_names
    cart = next(c for c in dpd["children"] if c["name"] == "Car-T")
    assert cart["count"] == 2


def test_no_second_line():
    rows = [
        {"first_line_therapy": "VRd", "second_line_therapy": None, "later_therapy": None},
        {"first_line_therapy": "DRd", "second_line_therapy": None, "later_therapy": None},
    ]
    result = compute(qs(rows))
    assert result["total"] == 2
    for child in result["children"]:
        assert child["children"] == []


def test_sort_order():
    rows = [
        {"first_line_therapy": "Rare",   "second_line_therapy": None, "later_therapy": None},
        {"first_line_therapy": "Common", "second_line_therapy": "A",  "later_therapy": None},
        {"first_line_therapy": "Common", "second_line_therapy": "A",  "later_therapy": None},
        {"first_line_therapy": "Common", "second_line_therapy": "B",  "later_therapy": None},
        {"first_line_therapy": "Common", "second_line_therapy": "A",  "later_therapy": None},
    ]
    result = compute(qs(rows))
    assert result["children"][0]["name"] == "Common"  # 4 patients
    common = result["children"][0]
    assert common["children"][0]["name"] == "A"       # 3 vs 1
    assert common["children"][0]["count"] == 3


def test_skips_null_first_line():
    rows = [
        {"first_line_therapy": None,  "second_line_therapy": None, "later_therapy": None},
        {"first_line_therapy": "VRd", "second_line_therapy": None, "later_therapy": None},
    ]
    result = compute(qs(rows))
    assert result["total"] == 1
    assert result["children"][0]["name"] == "VRd"
