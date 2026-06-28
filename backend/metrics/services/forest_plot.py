"""
Forest plot: per-subgroup OS hazard ratios with 95% CI (Peto method).
Each row compares a binary split of the cohort on a clinical variable.
"""
from django.db.models import Q

from metrics.services.km_utils import log_rank_hr
from metrics.services.survival import _os_times_events

_MIN_PER_ARM = 5  # skip row if either arm has fewer than this many OS observations


def _row(subgroup, comparison, reference, te_comp, te_ref):
    if len(te_comp) < _MIN_PER_ARM or len(te_ref) < _MIN_PER_ARM:
        return None
    result = log_rank_hr(te_comp, te_ref)
    if result is None:
        return None
    hr, ci_low, ci_high, p = result
    return {
        "subgroup":     subgroup,
        "comparison":   comparison,
        "reference":    reference,
        "n_comparison": len(te_comp),
        "n_reference":  len(te_ref),
        "hr":           hr,
        "ci_low":       ci_low,
        "ci_high":      ci_high,
        "p_value":      p,
    }


def compute(qs):
    splits = [
        # (subgroup label, comparison label, reference label, comp filter Q, ref filter Q)
        (
            "ER Status", "ER Positive", "ER Negative",
            Q(estrogen_receptor_status__icontains="positive"),
            Q(estrogen_receptor_status__icontains="negative"),
        ),
        (
            "HER2 Status", "HER2 Positive", "HER2 Negative",
            Q(her2_status__icontains="positive"),
            Q(her2_status__icontains="negative"),
        ),
        (
            "TNBC", "TNBC", "Non-TNBC",
            Q(tnbc_status=True),
            Q(tnbc_status=False),
        ),
        (
            "Stage", "Late (III/IV)", "Early (I/II)",
            Q(stage__iregex=r"stage\s+(iii|iv)"),
            Q(stage__iregex=r"stage\s+i{1,2}(\s|$)"),
        ),
        (
            "Age", "≥50 years", "<50 years",
            Q(patient_age__gte=50),
            Q(patient_age__lt=50),
        ),
        (
            "MRD Status", "MRD Negative", "MRD Positive",
            Q(mrd_status__icontains="negative"),
            Q(mrd_status__icontains="positive"),
        ),
    ]

    rows = []
    for subgroup, comp_label, ref_label, comp_q, ref_q in splits:
        te_comp = _os_times_events(qs.filter(comp_q))
        te_ref  = _os_times_events(qs.filter(ref_q))
        row = _row(subgroup, comp_label, ref_label, te_comp, te_ref)
        if row:
            rows.append(row)

    return rows
