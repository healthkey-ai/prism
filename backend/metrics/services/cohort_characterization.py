"""
Cohort Characterization (Table 1): structured baseline summary of the cohort.
Mirrors the first table in a clinical publication.
"""


def _median_iqr(values):
    if not values:
        return None, None, None
    s = sorted(values)
    n = len(s)
    med = s[n // 2] if n % 2 == 1 else (s[n // 2 - 1] + s[n // 2]) / 2.0
    q1  = s[n // 4]
    q3  = s[3 * n // 4]
    return round(med, 1), round(q1, 1), round(q3, 1)


def _pct(num, denom):
    if not denom:
        return None
    return round(100.0 * num / denom, 1)


def compute(qs):
    rows = list(qs.values(
        "patient_age", "gender",
        "estrogen_receptor_status", "her2_status", "tnbc_status",
        "stage", "ecog_performance_status", "mrd_status",
        "hemoglobin_g_dl", "serum_creatinine_mg_dl", "beta2_microglobulin",
        "second_line_therapy", "later_therapy",
    ))
    n = len(rows)
    if n == 0:
        return {"n": 0}

    # ── demographics ──────────────────────────────────────────────────────────
    ages   = [r["patient_age"] for r in rows if r["patient_age"] is not None]
    age_med, age_q1, age_q3 = _median_iqr(ages)
    female = sum(1 for r in rows if (r["gender"] or "").upper() in ("F", "FEMALE"))

    # ── receptor status (breast cancer) ───────────────────────────────────────
    er_tested   = [r for r in rows if r["estrogen_receptor_status"]]
    er_pos      = sum(1 for r in er_tested if "positive" in (r["estrogen_receptor_status"] or "").lower())
    her2_tested = [r for r in rows if r["her2_status"]]
    her2_pos    = sum(1 for r in her2_tested if "positive" in (r["her2_status"] or "").lower())
    tnbc_tested = [r for r in rows if r["tnbc_status"] is not None]
    tnbc_n      = sum(1 for r in tnbc_tested if r["tnbc_status"])

    # ── stage ─────────────────────────────────────────────────────────────────
    stage_counts: dict = {}
    for r in rows:
        s = r["stage"]
        if s:
            stage_counts[s] = stage_counts.get(s, 0) + 1
    stages = [
        {"stage": s, "n": cnt, "pct": _pct(cnt, n)}
        for s, cnt in sorted(stage_counts.items(), key=lambda x: -x[1])
    ]

    # ── ECOG ──────────────────────────────────────────────────────────────────
    ecog_counts: dict = {}
    for r in rows:
        e = r["ecog_performance_status"]
        if e is not None:
            ecog_counts[e] = ecog_counts.get(e, 0) + 1
    ecog = [
        {"score": e, "n": cnt, "pct": _pct(cnt, n)}
        for e, cnt in sorted(ecog_counts.items())
    ]

    # ── treatment lines ───────────────────────────────────────────────────────
    received_2l = sum(1 for r in rows if r["second_line_therapy"])
    received_3l = sum(1 for r in rows if r["later_therapy"])

    # ── MRD ───────────────────────────────────────────────────────────────────
    mrd_tested = [r for r in rows if r["mrd_status"]]
    mrd_neg    = sum(1 for r in mrd_tested if "negative" in (r["mrd_status"] or "").lower())
    mrd_pos    = sum(1 for r in mrd_tested if "positive" in (r["mrd_status"] or "").lower())

    # ── labs ──────────────────────────────────────────────────────────────────
    hgb  = [float(r["hemoglobin_g_dl"])      for r in rows if r["hemoglobin_g_dl"]      is not None]
    cr   = [float(r["serum_creatinine_mg_dl"]) for r in rows if r["serum_creatinine_mg_dl"] is not None]
    b2m  = [float(r["beta2_microglobulin"])   for r in rows if r["beta2_microglobulin"]  is not None]
    hgb_med,  hgb_q1,  hgb_q3  = _median_iqr(hgb)
    cr_med,   cr_q1,   cr_q3   = _median_iqr(cr)
    b2m_med,  b2m_q1,  b2m_q3  = _median_iqr(b2m)

    return {
        "n": n,
        "demographics": {
            "age_median": age_med, "age_q1": age_q1, "age_q3": age_q3,
            "female_n": female, "female_pct": _pct(female, n),
        },
        "receptor_status": {
            "er_positive_n": er_pos,   "er_positive_pct":  _pct(er_pos,   len(er_tested)),
            "er_tested": len(er_tested),
            "her2_positive_n": her2_pos, "her2_positive_pct": _pct(her2_pos, len(her2_tested)),
            "her2_tested": len(her2_tested),
            "tnbc_n": tnbc_n,           "tnbc_pct":          _pct(tnbc_n,   len(tnbc_tested)),
            "tnbc_tested": len(tnbc_tested),
        },
        "stages": stages,
        "ecog": ecog,
        "treatment": {
            "received_2l_n": received_2l, "received_2l_pct": _pct(received_2l, n),
            "received_3l_n": received_3l, "received_3l_pct": _pct(received_3l, n),
        },
        "mrd": {
            "negative_n": mrd_neg, "negative_pct": _pct(mrd_neg, len(mrd_tested)),
            "positive_n": mrd_pos, "positive_pct": _pct(mrd_pos, len(mrd_tested)),
            "tested": len(mrd_tested),
        },
        "labs": {
            "hemoglobin_median": hgb_med, "hemoglobin_q1": hgb_q1, "hemoglobin_q3": hgb_q3,
            "creatinine_median": cr_med,  "creatinine_q1": cr_q1,  "creatinine_q3": cr_q3,
            "b2m_median": b2m_med,        "b2m_q1": b2m_q1,        "b2m_q3": b2m_q3,
        },
    }
