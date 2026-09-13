"""B: 銘柄×スコアの累積パネル更新"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from em_market_weekly.data.calendar import business_days
from em_market_weekly.data.exposures import gem3_sector
from em_market_weekly.data.holdings import account_hold_daily
from em_market_weekly.data.rga_index import rga_bm_weight, rga_calendar
from em_market_weekly.data.security_master import code_change
from em_market_weekly.data.universe_files import (
    read_rga_universe,
    read_sedol_map,
    sedol_forward_map,
    sedol_reverse_map,
)
from em_market_weekly.dates import nearest_on_or_before
from em_market_weekly.features import universe as U
from em_market_weekly.features.bigdata_score import compute_bigdata_scores
from em_market_weekly.pipelines.context import Context


@dataclass
class UniverseInputs:
    """日付に依らない入力 (1 回だけ読んで営業日ループで使い回す)

    Attributes:
        universe: ``prepare_universe`` 済みの RGA ユニバース。
        sedol_forward: 保有 SEDOL → ユニバース SEDOL。
        rga_dates: RGA 構成データが存在する日付。
    """

    universe: pd.DataFrame
    sedol_forward: pd.Series
    rga_dates: list[int]


def load_universe_inputs(ctx: Context) -> UniverseInputs:
    """xlsx 2 つと RGA カレンダーを読む。

    Args:
        ctx: 実行コンテキスト。

    Returns:
        入力一式。
    """
    settings = ctx.settings
    sedol_map = read_sedol_map(settings.resolve(settings.input.sedol_map))
    universe = U.prepare_universe(
        read_rga_universe(settings.resolve(settings.input.rga_universe)),
        sedol_reverse_map(sedol_map),
    )
    return UniverseInputs(universe, sedol_forward_map(sedol_map), rga_calendar())


def universe_score(ctx: Context, ymd: int, inputs: UniverseInputs | None = None) -> pd.DataFrame:
    """1 日分の銘柄×スコアパネルを作る。

    ``archive/BLF.RGA_universe_score(dateymd)`` の置き換え。
    ``ymd`` が RGA データの無い日なら直前の営業日に丸める。

    Args:
        ctx: 実行コンテキスト。
        ymd: 基準日 (``YYYYMMDD``)。
        inputs: 日付に依らない入力。``None`` なら読み込む。

    Returns:
        ``UNIVERSE_SCORE_COLUMNS`` を列に持つ DataFrame。``index.name`` は実際の日付。
    """
    settings = ctx.settings
    inputs = load_universe_inputs(ctx) if inputs is None else inputs
    ymd = nearest_on_or_before(inputs.rga_dates, ymd)
    account_cd = settings.account_cd(ymd)

    rga = rga_bm_weight(ymd, inputs.sedol_forward)
    holdings = account_hold_daily(ymd, account_cd)

    score, score_ymd = ctx.scores.ai_score_daily(ymd)
    ctx.log(f"AI score file: {score_ymd}")
    score = score.merge(
        code_change(ymd, score["bid"].tolist(), "bid")[["bid", "sedol"]], on="bid", how="outer"
    )

    df = U.link_rga_universe(inputs.universe, rga)
    df = U.link_positions(df, holdings)
    df = U.add_active_weight(df)
    df = U.link_ai_score(df, score)
    df = U.attach_bid(df, code_change(ymd, df["sedol"].dropna().tolist(), "sedol"))
    df = U.attach_sector(df, gem3_sector(ymd))

    bigdata, bigdata_ymd = ctx.scores.bigdata_daily(ymd)
    ctx.log(f"BigData file: {bigdata_ymd}")
    df = U.attach_bigdata(df, compute_bigdata_scores(bigdata))

    df = U.finalize_columns(df)
    df.index.name = str(ymd)
    return df


def run(ctx: Context, to_ymd: int, from_ymd: int | None = None) -> Path:
    """累積パネルを ``to_ymd`` まで更新して保存する。

    ``archive/BLF.update_score_cumlative(to_ymd)`` の置き換え。既存の最新ファイルの
    日付から ``to_ymd`` までの営業日分を計算し、重複する初日を除いて連結する。
    ``ctx.recompute`` が有効なら既存ファイルを使わず ``from_ymd`` から作り直す。

    Args:
        ctx: 実行コンテキスト。
        to_ymd: 更新終了日。
        from_ymd: 既存ファイルが無い場合 (または再計算時) の開始日。

    Returns:
        保存した CSV のパス。

    Raises:
        ValueError: 開始日が決められない場合。
    """
    latest = None if ctx.recompute else ctx.paths.latest_score_cumulative()
    if latest is not None:
        existing = pd.read_csv(latest)
        start = int(latest.stem)
        ctx.log(f"Existing panel: {latest}")
    else:
        if from_ymd is None:
            raise ValueError("No existing cumulative panel. Specify from_ymd to bootstrap.")
        existing = pd.DataFrame()
        start = from_ymd

    inputs = load_universe_inputs(ctx)
    frames = []
    for ymd in business_days(ctx.settings.benchmark, start, to_ymd):
        ctx.log(f"universe_score: {ymd}")
        df = universe_score(ctx, ymd, inputs)
        df["date"] = ymd
        frames.append(df)
    new = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    if not existing.empty and not new.empty and existing.iloc[-1]["date"] == new.iloc[0]["date"]:
        new = new[new["date"] != new.iloc[0]["date"]]

    out = pd.concat([existing, new], ignore_index=True)
    path = ctx.paths.score_cumulative(to_ymd)
    out.to_csv(path, index=False)
    ctx.log(f"Save to {path}")
    return path
