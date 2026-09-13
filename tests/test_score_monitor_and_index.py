import numpy as np
import pandas as pd

from em_market_weekly.features.index_return import cumulative_return_difference, tail_cumulative
from em_market_weekly.features.score_monitor import active_weight_corr, ic_by_date, rebalance_corr


def test_ic_by_date():
    ret = pd.DataFrame(
        {
            "date": ["d1"] * 3 + ["d2"] * 3,
            "bid": list("abc") * 2,
            "return_price_usd": [1, 2, 3, 3, 2, 1],
        }
    )
    first = pd.DataFrame({"bid": list("abc"), "value": [1, 2, 3]})
    ic = ic_by_date(ret, first)
    np.testing.assert_allclose(ic.loc["d1", "c"], 1.0)
    np.testing.assert_allclose(ic.loc["d2", "c"], -1.0)


def test_rebalance_corr():
    score = pd.DataFrame(
        {
            "dateymd": [1] * 3 + [2] * 3 + [3] * 3,
            "bid": list("abc") * 3,
            "value": [1, 2, 3, 1, 2, 3, 3, 2, 1],
        }
    )
    reb = rebalance_corr(score, 2)
    assert list(reb.index) == [2, 3]
    np.testing.assert_allclose(reb["c"].values, [1.0, -1.0])


def test_active_weight_corr_excludes_zero_and_filters_date():
    panel = pd.DataFrame(
        {
            "date": [1, 1, 1, 1, 2, 2, 2],
            "Active": [1, 2, 3, 0, 1, 2, 3],
            "AI": [1, 2, 3, 100, 3, 2, 1],
        }
    )
    out = active_weight_corr(panel, "AI", 2)
    assert list(out.columns) == ["date", "Correlation"]
    assert out["date"].tolist() == [2]
    np.testing.assert_allclose(out["Correlation"].values, [-1.0])


def test_tail_cumulative_and_difference():
    dates = pd.date_range("2026-01-01", periods=4)
    a = pd.DataFrame({"Dates": dates, "Close": [1.0, 1.1, 1.21, 1.331]})
    a["Rtn"] = a["Close"].pct_change()
    b = pd.DataFrame({"Dates": dates, "Price": [1.0, 1.0, 1.0, 1.0]})
    b["Rtn"] = b["Price"].pct_change()
    at = tail_cumulative(a, "Close", 3)
    bt = tail_cumulative(b, "Price", 3)
    np.testing.assert_allclose(at["cumret"].iloc[-1], 1.331 / 1.1 - 1)
    diff = cumulative_return_difference(at, bt)
    np.testing.assert_allclose(diff["cumdiff"].iloc[-1], 0.1 * 3 * 100, rtol=1e-6)
