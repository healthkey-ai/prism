from collections import defaultdict


def _short(name):
    if not name:
        return None
    idx = name.find(" (")
    return name[:idx] if idx > 0 else name[:30]


def compute(qs):
    rows = list(qs.values('first_line_therapy', 'second_line_therapy', 'later_therapy'))

    counts_1l = defaultdict(int)
    counts_2l = defaultdict(lambda: defaultdict(int))
    counts_3l = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    for r in rows:
        first = _short(r.get('first_line_therapy'))
        if not first:
            continue
        counts_1l[first] += 1
        second = _short(r.get('second_line_therapy'))
        if second:
            counts_2l[first][second] += 1
            later = _short(r.get('later_therapy'))
            if later:
                counts_3l[first][second][later] += 1

    children = []
    for t1, c1 in sorted(counts_1l.items(), key=lambda x: -x[1]):
        children_2l = []
        for t2, c2 in sorted(counts_2l[t1].items(), key=lambda x: -x[1]):
            children_3l = [
                {"name": t3, "count": c3}
                for t3, c3 in sorted(counts_3l[t1][t2].items(), key=lambda x: -x[1])
            ]
            children_2l.append({"name": t2, "count": c2, "children": children_3l})
        children.append({"name": t1, "count": c1, "children": children_2l})

    return {"total": sum(counts_1l.values()), "children": children}
