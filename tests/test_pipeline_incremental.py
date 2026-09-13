"""増分計算が全期間計算と同じ結果になることの確認 (DB / SFTP は偽装)"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from em_market_weekly.constants import SCORE_TYPES
from em_market_weekly.pipelines import factor_return, score_monitor
from em_market_weekly.pipelines.context import Context
from em_market_weekly.settings import Settings

DAYS = [20260824, 20260825, 20260826, 20260827, 20260828, 20260831, 20260901, 20260902]
BIDS = [f"USA{i:03d}" for i in range(30)]


def _seed(*parts: int) -> int:
    return abs(hash(parts)) % (2**32)


class _FakeScores:
    """日付ごとに決定論的なスコアを返す ScoreStore の代役"""

    def __init__(self):
        self.calls: list[int] = []

    def ai_score_daily(self, ymd: int):
        self.calls.append(ymd)
        rng = np.random.default_rng(_seed(ymd, 1))
        df = pd.DataFrame({"bid": BIDS})
        for st in SCORE_TYPES:
            df[st] = rng.normal(size=len(BIDS))
        return df, ymd

    def close(self):
        pass


def _fake_business_days(bm: str, from_ymd: int, to_ymd: int) -> list[int]:
    return [d for d in DAYS if from_ymd <= d <= to_ymd]


def _fake_ret_global_daily(from_ymd: int, to_ymd: int, bids) -> pd.DataFrame:
    rows = []
    for d in _fake_business_days("", from_ymd, to_ymd):
        rng = np.random.default_rng(_seed(d, 2))
        for b in BIDS:
            rows.append(
                {
                    "date": f"{str(d)[:4]}-{str(d)[4:6]}-{str(d)[6:]}",
                    "bid": b,
                    "return_price_usd": rng.normal(),
                }
            )
    df = pd.DataFrame(rows)
    return df[df["bid"].isin(list(bids))].reset_index(drop=True)


def _fake_exposure_global(ym: int, bids, factors: list[str]) -> pd.DataFrame:
    rng = np.random.default_rng(_seed(ym, 3))
    values = pd.DataFrame(rng.normal(size=(len(BIDS), len(factors))), columns=factors)
    df = pd.concat([pd.DataFrame({"date": ym, "bid": BIDS}), values], axis=1)
    return df[df["bid"].isin(list(bids))].reset_index(drop=True)


@pytest.fixture
def ctx(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Context:
    settings.revision_window_days = 0
    c = Context(settings=settings, plot=False, verbose=False)
    c._scores = _FakeScores()
    monkeypatch.setattr(score_monitor, "business_days", _fake_business_days)
    monkeypatch.setattr(score_monitor, "ret_global_daily", _fake_ret_global_daily)
    monkeypatch.setattr(factor_return, "business_days", _fake_business_days)
    monkeypatch.setattr(
        factor_return, "ret_usd", lambda ymd, bids: _fake_ret_global_daily(ymd, ymd, bids)
    )
    monkeypatch.setattr("em_market_weekly.data.exposures.exposure_global", _fake_exposure_global)
    return c


def test_score_monitor_incremental_matches_full(ctx: Context):
    inception, reb = DAYS[0], DAYS[3]
    for to in (DAYS[4], DAYS[7]):
        pd.DataFrame(
            {
                "date": [to] * 3,
                "Active": [1, 2, 3],
                "AI": [1, 2, 3],
                "BigData": [3, 2, 1],
                "AI70_BD30": [1, 3, 2],
            }
        ).to_csv(ctx.paths.score_cumulative(to), index=False)

    score_monitor.run(ctx, inception, DAYS[4], reb, SCORE_TYPES)
    ctx._scores.calls.clear()
    inc = score_monitor.run(ctx, inception, DAYS[7], reb, SCORE_TYPES)
    # 増分: 読んだスコアは初日・リバランス日・新規 3 日のみ
    assert sorted(set(ctx._scores.calls)) == sorted({DAYS[0], DAYS[3], *DAYS[5:]})

    ctx.recompute = True
    full = score_monitor.run(ctx, inception, DAYS[7], reb, SCORE_TYPES)
    for st in SCORE_TYPES:
        pd.testing.assert_frame_equal(inc[st]["ic"], full[st]["ic"], check_dtype=False)
        pd.testing.assert_frame_equal(
            inc[st]["rebalance"], full[st]["rebalance"], check_dtype=False
        )
        assert inc[st]["ic"]["date"].tolist() == [
            f"{str(d)[:4]}-{str(d)[4:6]}-{str(d)[6:]}" for d in DAYS
        ]
        assert inc[st]["rebalance"]["dateymd"].tolist() == DAYS[3:]


def test_run_common_incremental_matches_full(ctx: Context):
    first = factor_return.run_common(ctx, DAYS[0], DAYS[4])
    assert first["ymd"].tolist() == DAYS[:5]
    ctx._scores.calls.clear()
    inc = factor_return.run_common(ctx, DAYS[0], DAYS[7])
    assert ctx._scores.calls == DAYS[5:]
    ctx.recompute = True
    full = factor_return.run_common(ctx, DAYS[0], DAYS[7])
    pd.testing.assert_frame_equal(inc, full, check_dtype=False)
    assert ctx.paths.factor_rtn_common(DAYS[0], DAYS[7]).exists()
