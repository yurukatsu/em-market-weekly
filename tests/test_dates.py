import pytest

from em_market_weekly import dates


def test_previous_month_across_year():
    assert dates.previous_month(20260105) == 202512


def test_shift_month_forward():
    assert dates.shift_month(202611, 3) == 202702


def test_nearest_on_or_before_exact_and_earlier():
    cands = [20260828, 20260831, 20260901]
    assert dates.nearest_on_or_before(cands, 20260831) == 20260831
    assert dates.nearest_on_or_before(cands, 20260830) == 20260828


def test_nearest_on_or_before_raises():
    with pytest.raises(ValueError):
        dates.nearest_on_or_before([20260901], 20260101)


def test_month_ends_drops_last():
    days = [20260129, 20260130, 20260227, 20260302, 20260331]
    assert dates.month_ends(days) == [20260130, 20260227]
    assert dates.month_ends(days, drop_last=False) == [20260130, 20260227, 20260331]


def test_shift_days_and_iso():
    assert dates.shift_days(20260301, -1) == 20260228
    assert dates.ymd_to_iso(20260301) == "2026-03-01"
