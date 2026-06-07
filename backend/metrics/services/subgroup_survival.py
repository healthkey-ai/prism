from django.db.models import Q
from metrics.services.survival import os_km, pfs_km

HIGH_RISK_CYTO = (
    Q(cytogenic_markers__icontains='del(17p)') |
    Q(cytogenic_markers__icontains='t(4;14)') |
    Q(cytogenic_markers__icontains='t(14;16)')
)

HAS_SCT = (
    ~Q(stem_cell_transplant_history__isnull=True) &
    ~Q(stem_cell_transplant_history=[])
)

NO_SCT = (
    Q(stem_cell_transplant_history__isnull=True) |
    Q(stem_cell_transplant_history=[])
)


def _subgroup_km(km_fn, subgroups):
    """
    Run km_fn on each (label, sub_qs) pair; drop subgroups with no observations.
    """
    result = []
    for label, sub_qs in subgroups:
        km = km_fn(sub_qs)
        if km["n"] > 0:
            result.append({"label": label, **km})
    return result


def _stage_subgroups(qs):
    stage_vals = (
        qs.exclude(stage__isnull=True)
        .exclude(stage="")
        .values_list("stage", flat=True)
        .distinct()
        .order_by("stage")
    )
    return [(val, qs.filter(stage=val)) for val in stage_vals]


def _cyto_subgroups(qs):
    return [
        ("High Risk",     qs.filter(HIGH_RISK_CYTO)),
        ("Standard Risk", qs.exclude(HIGH_RISK_CYTO)),
    ]


def _sct_subgroups(qs):
    return [
        ("SCT",    qs.filter(HAS_SCT)),
        ("No SCT", qs.filter(NO_SCT)),
    ]


def _stratify(qs, subgroups_fn):
    subs = subgroups_fn(qs)
    return {
        "os":  _subgroup_km(os_km,  subs),
        "pfs": _subgroup_km(pfs_km, subs),
    }


def compute(qs):
    return {
        "by_stage":        _stratify(qs, _stage_subgroups),
        "by_cytogenetics": _stratify(qs, _cyto_subgroups),
        "by_sct":          _stratify(qs, _sct_subgroups),
    }
