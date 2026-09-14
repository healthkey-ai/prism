from datetime import date

from metrics.services.survival import landmark_os_km


class _FakeQS:
    def __init__(self, rows):
        self.rows = rows

    def values(self, *fields):
        return [{f: row[f] for f in fields} for row in self.rows]


def test_landmark_os_draws_follow_up_without_recorded_deaths():
    qs = _FakeQS([
        {"first_line_start_date": date(2020, 1, 1), "death_date": None,
         "last_treatment": date(2021, 1, 1)},
        {"first_line_start_date": date(2020, 1, 1), "death_date": None,
         "last_treatment": date(2020, 4, 1)},
    ])
    result = landmark_os_km(qs)
    assert result["n"] == 1  # Earlier censoring cannot establish landmark survival.
    assert result["events"] == 0
    assert result["median"] is None
    assert [p["time"] for p in result["curve"]] == [0.0, 6.0]
    assert all(p["survival"] == 1.0 for p in result["curve"])
