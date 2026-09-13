"""factor_exposure.panel_for_date が累積パネルを再利用することの確認"""

import pandas as pd
import pytest

from em_market_weekly.pipelines import factor_exposure
from em_market_weekly.pipelines.context import Context
from em_market_weekly.settings import Settings


def test_panel_for_date_reuses_cumulative(settings: Settings, monkeypatch: pytest.MonkeyPatch):
    ctx = Context(settings=settings, verbose=False)
    panel = pd.DataFrame({"date": [20260828, 20260901], "bid": ["a", "b"], "BM": [1.0, 2.0]})
    panel.to_csv(ctx.paths.score_cumulative(20260901), index=False)

    called = []
    monkeypatch.setattr(factor_exposure, "universe_score", lambda c, y: called.append(y) or panel)

    out = factor_exposure.panel_for_date(ctx, 20260830)
    assert out["bid"].tolist() == ["a"] and "date" not in out.columns and called == []

    factor_exposure.panel_for_date(ctx, 20260905)  # パネルが期間を含まない -> 計算
    assert called == [20260905]

    ctx.recompute = True
    factor_exposure.panel_for_date(ctx, 20260830)
    assert called == [20260905, 20260830]
