"""C: ポートフォリオ / ベンチマークの共通ファクターエクスポージャ"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from em_market_weekly.constants import FACTOR_LIST
from em_market_weekly.data.exposures import exposure_global
from em_market_weekly.dates import previous_month
from em_market_weekly.features.factor_exposure import (
    normalize_exposures,
    weighted_category_averages,
)
from em_market_weekly.pipelines.context import Context
from em_market_weekly.pipelines.score_cumulative import universe_score


def panel_for_date(ctx: Context, ymd: int) -> pd.DataFrame:
    """``ymd`` 時点の銘柄×スコアパネルを返す。

    累積パネル (B の出力) が ``ymd`` を含んでいればそこから取り出し、
    無ければ ``universe_score`` で計算する。``ctx.recompute`` なら常に計算する。

    Args:
        ctx: 実行コンテキスト。
        ymd: 基準日。

    Returns:
        1 日分のパネル (``date`` 列なし)。
    """
    latest = None if ctx.recompute else ctx.paths.latest_score_cumulative()
    if latest is not None:
        panel = pd.read_csv(latest)
        if not panel.empty and panel["date"].max() >= ymd:
            day = panel.loc[panel["date"] <= ymd, "date"].max()
            ctx.log(f"Panel from {latest} ({day})")
            return panel[panel["date"] == day].drop(columns=["date"]).reset_index(drop=True)
    return universe_score(ctx, ymd)


def run(ctx: Context, from_ymd: int) -> Path:
    """``from_ymd`` 時点のパネルと前月末エクスポージャからカテゴリ平均を計算して保存する。

    ``archive/BLF.port_fct_exp(from_ymd)`` の置き換え。

    Args:
        ctx: 実行コンテキスト。
        from_ymd: 基準日。

    Returns:
        保存した CSV のパス。
    """
    ym = previous_month(from_ymd)
    panel = panel_for_date(ctx, from_ymd)
    bids = panel.dropna(subset=["bid"])["bid"].tolist()

    exposure = normalize_exposures(exposure_global(ym, bids, FACTOR_LIST))
    df = panel.merge(exposure, how="left", on="bid")
    result = weighted_category_averages(df)

    path = ctx.paths.factor_exp_common(from_ymd)
    result.to_csv(path, index=False)
    ctx.log(f"Save to {path}")
    return path


def load(ctx: Context, from_ymd: int) -> pd.DataFrame:
    """保存済みのカテゴリ平均 CSV を読む。"""
    return pd.read_csv(ctx.paths.factor_exp_common(from_ymd))
