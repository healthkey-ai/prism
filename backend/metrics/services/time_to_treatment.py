"""
Time to first treatment: days from diagnosis to 1st-line therapy start.
Reveals care access gaps and referral delays.
"""

_BINS = [
    (0,   30,  "0–30d"),
    (30,  60,  "30–60d"),
    (60,  90,  "60–90d"),
    (90,  180, "90–180d"),
    (180, 365, "180–365d"),
    (365, None, "365d+"),
]


def compute(qs):
    rows = list(qs.values("diagnosis_date", "first_line_start_date"))

    days_list = []
    for r in rows:
        if r["diagnosis_date"] and r["first_line_start_date"]:
            d = (r["first_line_start_date"] - r["diagnosis_date"]).days
            if d >= 0:
                days_list.append(d)

    if not days_list:
        return {"median_days": None, "n": 0, "histogram": []}

    s = sorted(days_list)
    n = len(s)
    median_days = s[n // 2] if n % 2 == 1 else (s[n // 2 - 1] + s[n // 2]) / 2.0

    histogram = []
    for lo, hi, label in _BINS:
        count = (
            sum(1 for d in days_list if d >= lo)
            if hi is None
            else sum(1 for d in days_list if lo <= d < hi)
        )
        histogram.append({"label": label, "count": count, "lo": lo, "hi": hi})

    return {
        "median_days": round(median_days),
        "n":           n,
        "histogram":   histogram,
    }
