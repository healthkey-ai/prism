from collections import Counter
from django.db.models import Count, Q


def _therapy_counts(qs, therapy_field, total):
    rows = (
        qs.exclude(**{f'{therapy_field}__isnull': True})
        .exclude(**{f'{therapy_field}__exact': ''})
        .values(therapy_field)
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    return [
        {"therapy": r[therapy_field], "count": r['count'],
         "pct": round(r['count'] / total * 100, 1) if total else 0}
        for r in rows
    ]


def _short(name):
    if not name:
        return "—"
    idx = name.find(" (")
    return name[:idx] if idx > 0 else name[:30]


def _build_sequences(qs):
    rows = qs.exclude(second_line_therapy__isnull=True).values(
        'first_line_therapy', 'second_line_therapy', 'later_therapy'
    )
    counter = Counter()
    for r in rows:
        parts = [_short(r['first_line_therapy']), _short(r['second_line_therapy'])]
        if r['later_therapy']:
            parts.append(_short(r['later_therapy']))
        counter[" → ".join(parts)] += 1
    return [{"sequence": seq, "count": cnt} for seq, cnt in counter.most_common(12)]


def compute(qs):
    total = qs.count()

    # Funnel + exact distribution — one aggregate() instead of 8 separate count() queries
    agg = qs.aggregate(
        ge1=Count('id', filter=Q(therapy_lines_count__gte=1)),
        ge2=Count('id', filter=Q(therapy_lines_count__gte=2)),
        ge3=Count('id', filter=Q(therapy_lines_count__gte=3)),
        ge4=Count('id', filter=Q(therapy_lines_count__gte=4)),
        eq1=Count('id', filter=Q(therapy_lines_count=1)),
        eq2=Count('id', filter=Q(therapy_lines_count=2)),
        eq3=Count('id', filter=Q(therapy_lines_count=3)),
        eq4=Count('id', filter=Q(therapy_lines_count=4)),
    )

    line_funnel = [
        {"line": n, "label": f"≥{n}L", "count": agg[f'ge{n}'],
         "pct": round(agg[f'ge{n}'] / total * 100, 1) if total else 0}
        for n in [1, 2, 3, 4]
    ]
    exact_dist = [
        {"lines": n, "label": f"{n}L", "count": agg[f'eq{n}'],
         "pct": round(agg[f'eq{n}'] / total * 100, 1) if total else 0}
        for n in [1, 2, 3, 4] if agg[f'eq{n}']
    ]

    return {
        "first_line":        _therapy_counts(qs, 'first_line_therapy', total),
        "second_line":       _therapy_counts(qs, 'second_line_therapy', total),
        "later_line":        _therapy_counts(qs, 'later_therapy', total),
        "line_funnel":       line_funnel,
        "line_distribution": exact_dist,
        "sequences":         _build_sequences(qs),
    }
