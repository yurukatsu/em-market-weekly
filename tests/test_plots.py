import numpy as np
import pandas as pd

from em_market_weekly.plots.cumulative_lines import (
    plot_common_factor_cumulative,
    plot_nam_factor_cumulative,
)
from em_market_weekly.plots.factor_exposure import plot_factor_exposure
from em_market_weekly.plots.index_return import plot_index_return
from em_market_weekly.plots.score_monitor import plot_score_monitor
from em_market_weekly.plots.style import close_all


def _ymds(n):
    return [int(d.strftime("%Y%m%d")) for d in pd.bdate_range("2026-08-03", periods=n)]


def test_common_and_nam_plots_render():
    rng = np.random.default_rng(0)
    ymds = _ymds(30)
    common = pd.DataFrame({"ymd": ymds, "BP_EST": rng.normal(size=30), "MOM1": rng.normal(size=30)})
    fig = plot_common_factor_cumulative(common, ymds[-5])
    assert len(fig.axes) == 1
    nam = pd.DataFrame(
        {
            "date": ymds,
            "ai": rng.normal(size=30),
            "ai70_bd30": rng.normal(size=30),
            "TVL": rng.normal(size=30),
            "rvl": rng.normal(size=30),
            "QIP": rng.normal(size=30),
        }
    )
    fig = plot_nam_factor_cumulative(nam, "date", ymds[-5], "t")
    labels = [t.get_text() for t in fig.axes[0].get_legend().get_texts()]
    assert "QIP" not in labels and set(labels) == {"ai", "ai70_bd30", "TVL", "rvl"}
    close_all()


def test_factor_exposure_and_monitor_and_index_render():
    rng = np.random.default_rng(1)
    ymds = _ymds(10)
    common = pd.DataFrame({"ymd": ymds, "BP_EST": rng.normal(size=10), "MOM1": rng.normal(size=10)})
    nam = pd.DataFrame({"date": ymds, "ai": rng.normal(size=10), "TVL": rng.normal(size=10)})
    exp = pd.DataFrame(
        {"Category": ["Stock Value", "Momentum"], "Active Weighted Average": [0.01, -0.02]}
    )
    fig = plot_factor_exposure(common, nam, exp)
    assert len(fig.axes) >= 2

    ic = pd.DataFrame({"date": [pd.Timestamp(str(d)) for d in ymds], "c": rng.normal(size=10)})
    reb = pd.DataFrame({"dateymd": ymds[5:], "c": rng.normal(size=5)})
    acw = pd.DataFrame({"date": ymds, "Correlation": rng.normal(size=10) / 10})
    fig = plot_score_monitor(ic, reb, acw, ymds[-3], ymds[5], "ai")
    assert len(fig.axes) == 3

    dates = pd.bdate_range("2026-01-01", periods=10)
    mk = lambda: pd.DataFrame(
        {"Dates": dates, "cumret": rng.normal(size=10), "Rtn": rng.normal(size=10)}
    )
    diff = pd.DataFrame({"Dates": dates, "cumdiff": rng.normal(size=10)})
    fig = plot_index_return(
        mk(), mk(), mk(), diff, int(dates[-3].strftime("%Y%m%d")), int(dates[-1].strftime("%Y%m%d"))
    )
    assert len(fig.axes) == 1
    close_all()
