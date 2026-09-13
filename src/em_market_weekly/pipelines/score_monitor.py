"""E: スコアモニター (IC / リバランス相関 / アクティブウェイト相関)

スコアファイルは 1 回だけ読み、3 種類のスコアをまとめて計算する。
IC とリバランス相関は日ごとに独立なので増分計算する。
"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from em_market_weekly.constants import SCORE_PANEL_COLUMNS, SCORE_TYPES
from em_market_weekly.data.calendar import business_days
from em_market_weekly.data.returns import ret_global_daily
from em_market_weekly.features.score_monitor import active_weight_corr, ic_by_date, rebalance_corr
from em_market_weekly.pipelines.context import Context
from em_market_weekly.pipelines.incremental import (
    Plan,
    load_kept_rows,
    make_plan,
    merge_rows,
)
from em_market_weekly.plots.score_monitor import plot_score_monitor


def load_scores(ctx: Context, days: Sequence[int]) -> pd.DataFrame:
    """指定日のスコアファイルを読み、縦に連結する。

    Args:
        ctx: 実行コンテキスト。
        days: 読む日付 (``YYYYMMDD``)。

    Returns:
        列 ``dateymd``, ``bid`` + ``SCORE_TYPES`` の DataFrame。
    """
    frames = []
    for ymd in days:
        score, _ = ctx.scores.ai_score_daily(ymd)
        score = score[["bid", *SCORE_TYPES]].copy()
        score.insert(0, "dateymd", ymd)
        frames.append(score)
    return pd.concat(frames, ignore_index=True)


def _shared_plan(ctx: Context, days: list[int], ends: list[int | None], to_ymd: int) -> Plan:
    """複数の前回出力に対して共通の計画を作る (1 つでも無ければ全期間)。"""
    existing_end = None if any(e is None for e in ends) else min(ends)  # type: ignore[type-var]
    return make_plan(
        days, existing_end, to_ymd, ctx.settings.revision_window_days, recompute=ctx.recompute
    )


def _iso_date(df: pd.DataFrame) -> pd.DataFrame:
    """``date`` 列を ``YYYY-MM-DD`` 文字列に揃える (CSV の既存行と型を合わせる)。"""
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    return out


def run(
    ctx: Context,
    inception_ymd: int,
    to_ymd: int,
    reb_ymd: int,
    score_types: Sequence[str] = SCORE_TYPES,
    from_ymd: int | None = None,
) -> dict[str, dict[str, pd.DataFrame]]:
    """IC・リバランス相関・アクティブウェイト相関を計算し、保存・描画する。

    ``archive/BLF.score_IC_Reb`` + ``ActiveWeight_score_Corr`` + ``plot_Score_monitor`` の置き換え。

    Args:
        ctx: 実行コンテキスト。
        inception_ymd: 計算開始日 (図の表示開始日)。
        to_ymd: 終了日。
        reb_ymd: リバランス日 (営業日でなければ直後の営業日に丸める)。
        score_types: 計算するスコア種別。
        from_ymd: 図の強調区間の開始日。``None`` なら描画しない。

    Returns:
        スコア種別 → ``{"ic": ..., "rebalance": ..., "active_weight": ...}``。

    Raises:
        ValueError: ``inception_ymd > reb_ymd`` の場合。
        FileNotFoundError: 累積パネル ``{to_ymd}.csv`` が無い場合。
    """
    if inception_ymd > reb_ymd:
        raise ValueError("inception_ymd must be earlier than or equal to reb_ymd.")
    settings = ctx.settings
    paths = ctx.paths
    days = business_days(settings.benchmark, inception_ymd, to_ymd)
    reb_true = business_days(settings.benchmark, reb_ymd, to_ymd)[0]
    reb_days = [d for d in days if d >= reb_true]

    ic_existing = {
        st: paths.latest_range_file(paths.score_ic_dir(st), "", inception_ymd, to_ymd)
        for st in score_types
    }
    reb_existing = {
        st: paths.latest_range_file(paths.rebalance_corr_dir(st), "", reb_true, to_ymd)
        for st in score_types
    }
    ic_plan = _shared_plan(ctx, days, [e[1] if e else None for e in ic_existing.values()], to_ymd)
    reb_plan = _shared_plan(
        ctx, reb_days, [e[1] if e else None for e in reb_existing.values()], to_ymd
    )
    ctx.log(
        f"IC: compute {len(ic_plan.compute_days)} days, "
        f"rebalance corr: compute {len(reb_plan.compute_days)} days"
    )

    needed = sorted({days[0], reb_true, *ic_plan.compute_days, *reb_plan.compute_days})
    scores = load_scores(ctx, needed)
    score_first = scores[scores["dateymd"] == days[0]]

    ret = None
    if ic_plan.compute_days:
        ret = ret_global_daily(
            ic_plan.compute_days[0], to_ymd, score_first["bid"].unique().tolist()
        )

    panel_path = paths.score_cumulative(to_ymd)
    if not panel_path.exists():
        raise FileNotFoundError(
            f"Cumulative panel not found: {panel_path}. Run score-cumulative first."
        )
    panel = pd.read_csv(panel_path)

    results: dict[str, dict[str, pd.DataFrame]] = {}
    for st in score_types:
        first = score_first[["bid", st]].rename(columns={st: "value"})
        series = scores[["dateymd", "bid", st]].rename(columns={st: "value"})

        ic_new = (
            _iso_date(ic_by_date(ret, first).reset_index())
            if ret is not None
            else pd.DataFrame(columns=["date", "c"])
        )
        ic = merge_rows(
            load_kept_rows(ic_existing[st][0] if ic_existing[st] else None, "date", ic_plan),
            ic_new,
            "date",
        )
        ic_path = paths.score_ic(st, inception_ymd, to_ymd)
        ic.to_csv(ic_path, index=False)
        ctx.log(f"Save to {ic_path}")

        reb_new = (
            rebalance_corr(
                series[series["dateymd"].isin([reb_true, *reb_plan.compute_days])], reb_true
            ).reset_index()
            if reb_plan.compute_days
            else pd.DataFrame(columns=["dateymd", "c"])
        )
        reb = merge_rows(
            load_kept_rows(reb_existing[st][0] if reb_existing[st] else None, "dateymd", reb_plan),
            reb_new,
            "dateymd",
        )
        reb_path = paths.rebalance_corr(st, reb_true, to_ymd)
        reb.to_csv(reb_path, index=False)
        ctx.log(f"Save to {reb_path}")

        acw = active_weight_corr(panel, SCORE_PANEL_COLUMNS[st], inception_ymd)
        acw_path = paths.active_weight_corr(st, inception_ymd, to_ymd)
        acw.to_csv(acw_path, index=False)
        ctx.log(f"Save to {acw_path}")

        results[st] = {"ic": ic, "rebalance": reb, "active_weight": acw}
        if ctx.plot and from_ymd is not None:
            fig = plot_score_monitor(ic, reb, acw, from_ymd, reb_ymd, st)
            ctx.save_figure(fig, f"monitor_{st}")
    return results
