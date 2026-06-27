from collections import defaultdict


def _short(name):
    if not name:
        return '—'
    idx = name.find(' (')
    return name[:idx] if idx > 0 else name[:30]


def compute(qs):
    rows = qs.values('first_line_therapy', 'second_line_therapy', 'later_therapy')

    # Accumulate (l1, l2, l3) pathway counts
    counts: dict = defaultdict(int)
    for row in rows:
        l1 = _short(row.get('first_line_therapy') or '')
        if not l1 or l1 == '—':
            continue
        l2 = _short(row.get('second_line_therapy') or '')
        l3 = _short(row.get('later_therapy') or '')
        counts[(l1, l2, l3)] += 1

    if not counts:
        return {'name': 'root', 'children': []}

    # Group by l1
    l1_map: dict = defaultdict(list)
    for (l1, l2, l3), n in counts.items():
        l1_map[l1].append((l2, l3, n))

    def make_l3_children(l3_pairs):
        grouped: dict = defaultdict(int)
        for l3, n in l3_pairs:
            grouped[l3] += n
        # Sort: by value descending; '—' sorts last
        return sorted(
            [{'name': name, 'value': count} for name, count in grouped.items()],
            key=lambda x: (x['name'] == '—', -x['value'])
        )

    def make_l2_children(triples):
        l2_map: dict = defaultdict(list)
        for l2, l3, n in triples:
            l2_map[l2].append((l3, n))

        children = []
        for l2, l3_pairs in sorted(
            l2_map.items(),
            key=lambda x: (x[0] == '—', -sum(n for _, n in x[1]))
        ):
            total = sum(n for _, n in l3_pairs)
            if l2 == '—':
                children.append({'name': '—', 'value': total})
            else:
                l3_children = make_l3_children(l3_pairs)
                children.append({'name': l2, 'children': l3_children})
        return children

    root_children = []
    for l1, triples in sorted(
        l1_map.items(),
        key=lambda x: -sum(n for _, _, n in x[1])
    ):
        l2_children = make_l2_children(triples)
        root_children.append({'name': l1, 'children': l2_children})

    return {'name': 'root', 'children': root_children}
