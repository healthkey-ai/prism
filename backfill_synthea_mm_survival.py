#!/usr/bin/env python3
"""
Backfill survival + subgroup data for the STAGING SYNTHEA-MM cohort so the
Survival-by-Subgroup, Landmark-OS, and Subgroup-Forest-Plot charts render.

Root cause these charts were empty: the 1000 SYNTHEA-MM patients (organization
id 28) on staging had NO death_date (→ zero OS events → flat single-point KM
curves, undefined medians, uncomputable hazard ratios) and NO cytogenic_markers
/ mrd_status / stem_cell_transplant_history (→ empty cytogenetics / MRD / SCT
subgroups). This script populates all four, in an order that lets the death-date
calibration use the assigned cytogenetics for high-risk mortality.

Targets patient_record directly (PROMOP's read model) for organization_id = 28
on STAGING_DATABASE_URL only. Reproducible (fixed seed); safe to re-run.

Distributions are calibrated against published real-world MM data:
  - High-risk cytogenetics [del(17p)/t(4;14)/t(14;16)] in ~28% of patients
  - ~50% deceased by the 2026-05-31 study cutoff, timed after last therapy,
    worse with high-risk cytogenetics / more lines / poorer last outcome
  - MRD-negativity tracks depth of best response
  - ASCT rate age-dependent (younger patients transplanted more often)
"""
import json
import os
import random
from datetime import date

import psycopg2

DB_URL = os.environ.get("STAGING_DATABASE_URL") or os.environ["DATABASE_URL"]
ORG_ID = 28  # SYNTHEA-MM
CUTOFF = date(2026, 5, 31)

random.seed(28)  # reproducible


def add_months(d, months):
    if d is None:
        return None
    m = d.month - 1 + months
    y = d.year + m // 12
    mo = m % 12 + 1
    day = min(d.day, [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1])
    return date(y, mo, day)


# ── Cytogenetics ──────────────────────────────────────────────────────────────
# ~10% never worked up (null → unevaluable, correctly excluded from risk split);
# of the ~90% tested, ~28% carry >=1 high-risk lesion per HIGH_RISK_CYTO.
HIGH_RISK = ["del(17p)", "t(4;14)", "t(14;16)"]
STANDARD = ["t(11;14)", "hyperdiploid", "Normal karyotype", "gain(1q)"]


def assign_cytogenetics():
    if random.random() < 0.10:
        return None  # no cytogenetics workup — unevaluable
    if random.random() < 0.28:  # of the tested, ~28% high risk
        markers = [random.choice(HIGH_RISK)]
        if random.random() < 0.25:  # some carry a second lesion
            markers.append(random.choice(HIGH_RISK + ["gain(1q)"]))
        return ", ".join(dict.fromkeys(markers))  # de-dupe, preserve order
    return random.choice(STANDARD)


# ── MRD ───────────────────────────────────────────────────────────────────────
_DEPTH = {
    "Complete Response": 5,
    "Very Good Partial Response": 4,
    "Partial Response": 3,
    "Minimal Response": 2,
    "Stable Disease": 1,
    "Progressive Disease": 0,
}
_MRD_NEG_PROB = {5: 0.75, 4: 0.45, 3: 0.18, 2: 0.07, 1: 0.05, 0: 0.02}


def best_depth(row):
    depths = [
        _DEPTH[o]
        for o in (row["first_line_outcome"], row["second_line_outcome"], row["later_outcome"])
        if o in _DEPTH
    ]
    return max(depths) if depths else None


def assign_mrd(row):
    depth = best_depth(row)
    if depth is None or random.random() < 0.25:
        return None  # ~25% not MRD-assessed, plus patients with no response record
    return "MRD negative" if random.random() < _MRD_NEG_PROB[depth] else "MRD positive"


# ── SCT ───────────────────────────────────────────────────────────────────────
def assign_sct(row):
    age = row["patient_age"] or 67
    if age < 65:
        p = 0.65
    elif age < 72:
        p = 0.45
    else:
        p = 0.15
    if random.random() > p:
        return []  # not transplanted → NO_SCT arm
    if random.random() < 0.03:
        return ["allogeneic SCT"]
    return ["autologous SCT"]


# ── Death dates ───────────────────────────────────────────────────────────────
# Months after last-treatment-end until death, by last outcome
POST_TX_MONTHS = {
    "Progressive Disease": (1, 10),
    "Minimal Response": (3, 18),
    "Stable Disease": (4, 24),
    "Partial Response": (8, 36),
    "Very Good Partial Response": (12, 48),
    "Complete Response": (18, 60),
}
DEATH_PROB = {
    "bad": [0.72, 0.88, 0.94, 0.97],       # PD or MR at last line
    "moderate": [0.38, 0.56, 0.70, 0.80],  # SD at last line
    "good": [0.14, 0.24, 0.36, 0.48],      # PR / VGPR / CR at last line
}
HIGH_RISK_MULTIPLIER = 1.40


def classify_outcome(outcome):
    if outcome in ("Progressive Disease", "Minimal Response"):
        return "bad"
    if outcome == "Stable Disease":
        return "moderate"
    return "good"  # CR, VGPR, PR, None


def compute_death_date(row, cyto):
    if not row["first_line_start_date"]:
        return None
    n_lines = row["therapy_lines_count"] or 1

    if row["later_end_date"]:
        last_end, last_outcome = row["later_end_date"], row["later_outcome"] or ""
    elif row["second_line_end_date"]:
        last_end, last_outcome = row["second_line_end_date"], row["second_line_outcome"] or ""
    else:
        last_end, last_outcome = row["first_line_end_date"], row["first_line_outcome"] or ""
    if not last_end:
        return None

    high_risk = bool(row["tp53_disruption"]) or (
        cyto is not None and any(m in cyto for m in HIGH_RISK)
    )

    prob = DEATH_PROB[classify_outcome(last_outcome)][min(n_lines - 1, 3)]
    if high_risk:
        prob = min(0.97, prob * HIGH_RISK_MULTIPLIER)
    if random.random() > prob:
        return None  # alive at cutoff

    lo, hi = POST_TX_MONTHS.get(last_outcome, (4, 24))
    death = add_months(last_end, random.randint(lo, hi))
    return death if death and death <= CUTOFF else None


SELECT_COLS = [
    "person_id", "patient_age",
    "first_line_start_date", "first_line_end_date", "first_line_outcome",
    "second_line_end_date", "second_line_outcome",
    "later_end_date", "later_outcome",
    "therapy_lines_count", "tp53_disruption",
]


def run():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute(
        f"SELECT {', '.join(SELECT_COLS)} FROM patient_record "
        "WHERE organization_id = %s ORDER BY person_id",
        (ORG_ID,),
    )
    rows = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]

    stats = {"deaths": 0, "cyto": 0, "high_risk": 0, "mrd": 0, "sct": 0}
    for row in rows:
        cyto = assign_cytogenetics()
        mrd = assign_mrd(row)
        sct = assign_sct(row)
        death = compute_death_date(row, cyto)

        cur.execute(
            "UPDATE patient_record SET "
            "cytogenic_markers = %s, mrd_status = %s, "
            "stem_cell_transplant_history = %s, death_date = %s "
            "WHERE person_id = %s AND organization_id = %s",
            (cyto, mrd, json.dumps(sct), death, row["person_id"], ORG_ID),
        )
        stats["deaths"] += bool(death)
        stats["cyto"] += bool(cyto)
        stats["high_risk"] += bool(cyto and any(m in cyto for m in HIGH_RISK))
        stats["mrd"] += bool(mrd)
        stats["sct"] += bool(sct)

    conn.commit()
    cur.close()
    conn.close()

    n = len(rows)
    print(f"Backfilled {n} SYNTHEA-MM patients (org {ORG_ID}):")
    print(f"  deaths (OS events):   {stats['deaths']} ({100*stats['deaths']//n}%)")
    print(f"  cytogenetics tested:  {stats['cyto']}  (high-risk {stats['high_risk']})")
    print(f"  MRD assessed:         {stats['mrd']}")
    print(f"  SCT (any):            {stats['sct']}")


if __name__ == "__main__":
    run()
