import pytest
from metrics.services.treatment_pathways import compute


class _FakeQS:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def exclude(self, *args, **kwargs):
        return self

    def values_list(self, *fields, flat=False):
        if flat:
            return [r[fields[0]] for r in self._rows]
        return [tuple(r.get(f) for f in fields) for r in self._rows]

    def values(self, *fields):
        return [{f: r.get(f) for f in fields} for r in self._rows]

    def distinct(self):
        return self

    def order_by(self, *args):
        return self


def test_empty_queryset():
    result = compute(_FakeQS([]))
    assert result == {'name': 'root', 'children': []}


def test_happy_path_correct_structure():
    rows = [
        {'first_line_therapy': 'VRd', 'second_line_therapy': 'DPd', 'later_therapy': 'Isa-Pd'},
        {'first_line_therapy': 'VRd', 'second_line_therapy': 'DPd', 'later_therapy': 'Isa-Pd'},
        {'first_line_therapy': 'VRd', 'second_line_therapy': 'KRd', 'later_therapy': None},
    ]
    result = compute(_FakeQS(rows))

    assert result['name'] == 'root'
    assert len(result['children']) == 1

    vrd = result['children'][0]
    assert vrd['name'] == 'VRd'
    assert 'children' in vrd

    l2_names = [c['name'] for c in vrd['children']]
    assert 'DPd' in l2_names
    assert 'KRd' in l2_names

    dpd = next(c for c in vrd['children'] if c['name'] == 'DPd')
    assert 'children' in dpd
    isa_pd = next(c for c in dpd['children'] if c['name'] == 'Isa-Pd')
    assert isa_pd['value'] == 2


def test_discontinued_at_1l():
    rows = [
        {'first_line_therapy': 'VRd', 'second_line_therapy': None, 'later_therapy': None},
        {'first_line_therapy': 'VRd', 'second_line_therapy': None, 'later_therapy': None},
    ]
    result = compute(_FakeQS(rows))

    vrd = result['children'][0]
    assert vrd['name'] == 'VRd'

    dash = next(c for c in vrd['children'] if c['name'] == '—')
    assert dash['value'] == 2
    assert 'children' not in dash


def test_discontinued_at_2l():
    rows = [
        {'first_line_therapy': 'VRd', 'second_line_therapy': 'DPd', 'later_therapy': None},
        {'first_line_therapy': 'VRd', 'second_line_therapy': 'DPd', 'later_therapy': None},
    ]
    result = compute(_FakeQS(rows))

    vrd = result['children'][0]
    dpd = next(c for c in vrd['children'] if c['name'] == 'DPd')
    assert 'children' in dpd

    l3_names = [c['name'] for c in dpd['children']]
    assert '—' in l3_names

    dash = next(c for c in dpd['children'] if c['name'] == '—')
    assert dash['value'] == 2


def test_l1_sorting_largest_first():
    rows = (
        [{'first_line_therapy': 'Small', 'second_line_therapy': None, 'later_therapy': None}]
        + [{'first_line_therapy': 'Big', 'second_line_therapy': None, 'later_therapy': None}] * 5
    )
    result = compute(_FakeQS(rows))

    assert result['children'][0]['name'] == 'Big'
    assert result['children'][1]['name'] == 'Small'


def test_dash_sorts_last_in_l2():
    rows = [
        {'first_line_therapy': 'VRd', 'second_line_therapy': None, 'later_therapy': None},
        {'first_line_therapy': 'VRd', 'second_line_therapy': 'DPd', 'later_therapy': None},
        {'first_line_therapy': 'VRd', 'second_line_therapy': 'DPd', 'later_therapy': None},
        {'first_line_therapy': 'VRd', 'second_line_therapy': 'DPd', 'later_therapy': None},
    ]
    result = compute(_FakeQS(rows))

    vrd = result['children'][0]
    l2_names = [c['name'] for c in vrd['children']]
    # DPd has 3 patients, '—' has 1; '—' should sort last
    assert l2_names[-1] == '—'
    assert l2_names[0] == 'DPd'


def test_no_first_line_therapy_skipped():
    rows = [
        {'first_line_therapy': None, 'second_line_therapy': 'DPd', 'later_therapy': None},
        {'first_line_therapy': '', 'second_line_therapy': 'DPd', 'later_therapy': None},
    ]
    result = compute(_FakeQS(rows))
    assert result == {'name': 'root', 'children': []}
