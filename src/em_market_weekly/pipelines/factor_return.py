"""D: ファクターリターン (共通ファクター / NAM ファクター)

どちらも日ごとに独立した値なので増分計算する (``pipelines.incremental`` 参照)。
"""

from __future__ import annotations

import pandas as pd

from em_market_weekly.constants import (
    CALENDAR_END_YMD,
    FACTOR_LIST,
    NAM_CALENDAR_START_YMD,
    NAM_FACTORS,
    TVL_FACTOR_ID,
)
from em_market_weekly.data.calendar import business_days
from em_market_weekly.data.exposures import (
    MonthlyExposureCache,
    factor_glb_raw,
    latest_factor_glb_date,
)
from em_market_weekly.data.returns import ret_global_daily, ret_usd, sret_global_daily
from em_market_weekly.data.universe_files import read_region_map
from em_market_weekly.dates import month_ends, previous_month
from em_market_weekly.features.factor_exposure import normalize_exposures
from em_market_weekly.features.factor_return import daily_factor_returns
from em_market_weekly.features.nam_factor_return import (
    assign_quantiles,
    demean_by_date,
    expand_month_end_exposures,
    top_quantile_returns,
)
from em_market_weekly.features.transforms import blom_score
from em_market_weekly.pipelines.context import Context
from em_market_weekly.pipelines.incremental import Plan, load_kept_rows, make_plan, merge_rows
from em_market_weekly.plots.cumulative_lines import (
    plot_common_factor_cumulative,
    plot_nam_factor_cumulative,
)
from em_market_weekly.plots.factor_exposure import plot_factor_exposure

KIND_NAM_EXPOSURE = "nam_exposure"


def _plan(ctx: Context, days: list[int], existing_end: int | None, to_ymd: int) -> Plan:
    plan = make_plan(
        days, existing_end, to_ymd, ctx.settings.revision_window_days, recompute=ctx.recompute
    )
    if plan.full:
        ctx.log(f"Full computation: {len(plan.compute_days)} days")
    else:
        ctx.log(f"Incremental: keep <= {plan.cutoff}, compute {len(plan.compute_days)} days")
    return plan


# ----------------------------------------------------------------------
# 共通ファクター
# ----------------------------------------------------------------------
def run_common(ctx: Context, from_ymd: int, to_ymd: int) -> pd.DataFrame:
    """共通ファクターの日次リターンを計算して保存する。

    ``archive/BLF.fret_em_daily(from_ymd, to_ymd)`` の置き換え。前回出力
    ``fret_D_{from_ymd}_{X}.csv`` があれば、改訂ウィンドウ外の行は再利用する。

    Args:
        ctx: 実行コンテキスト。
        from_ymd: 開始日。
        to_ymd: 終了日。

    Returns:
        列 ``ymd`` + ファクター列の DataFrame (保存内容と同じ)。
    """
    settings = ctx.settings
    days = business_days(settings.benchmark, from_ymd, to_ymd)
    existing = ctx.paths.latest_range_file(
        ctx.paths.factor_rtn_common_dir, "fret_D_", from_ymd, to_ymd
    )
    plan = _plan(ctx, days, existing[1] if existing else None, to_ymd)
    kept = load_kept_rows(existing[0] if existing else None, "ymd", plan)

    exposures = MonthlyExposureCache(FACTOR_LIST)
    rows = []
    for ymd in plan.compute_days:
        ctx.log(f"common factor return: {ymd}")
        score, _ = ctx.scores.ai_score_daily(ymd)
        bids = score.dropna(subset=["bid"])["bid"].tolist()
        exposure = normalize_exposures(exposures.get(previous_month(ymd), bids)).reset_index()
        ret = ret_usd(ymd, exposure["bid"].tolist())
        row = daily_factor_returns(ret, exposure).to_frame().T.reset_index(drop=True)
        row.columns.name = None
        row.insert(0, "ymd", ymd)
        rows.append(row)
    new = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["ymd"])

    total = merge_rows(kept, new, "ymd")
    path = ctx.paths.factor_rtn_common(from_ymd, to_ymd)
    total.to_csv(path, index=False)
    ctx.log(f"Save to {path}")
    return total


# ----------------------------------------------------------------------
# NAM ファクター
# ----------------------------------------------------------------------
def _build_month_end_exposure(
    ctx: Context, exp_date: int, region_map: pd.DataFrame
) -> pd.DataFrame:
    """1 つの月末時点の NAM ファクターエクスポージャ (ai / ai70_bd30 / TVL / rvl / QIP) を作る。"""
    settings = ctx.settings
    ai, _ = ctx.scores.ai_score_daily(exp_date)
    ai = ai[["bid", "ai", "ai70_bd30"]].copy()
    ai["ctry"] = ai["bid"].str[:3]
    ai = ai.merge(region_map, on="ctry", how="left")

    tvl = factor_glb_raw(latest_factor_glb_date(exp_date, TVL_FACTOR_ID), TVL_FACTOR_ID, "TVL")

    bigdata, _ = ctx.scores.bigdata_daily(exp_date, fallback_ymd=settings.bigdata_min_ymd)
    rvl = bigdata[["bid", "rvl"]]

    qip = ctx.scores.qip_monthly(previous_month(exp_date))
    qip["inv_to_ta"] = qip["invention_count_12m"] / qip["tassets"]
    qip["QIP"] = blom_score(qip["inv_to_ta"])

    unv = (
        ai.merge(tvl, on="bid", how="left")
        .merge(rvl, on="bid", how="left")
        .merge(qip[["bid", "QIP"]], on="bid", how="left")
    )
    unv["exp_date"] = exp_date
    return unv.dropna(subset=["bid"]).reset_index(drop=True)


def month_end_exposures(ctx: Context, ends: list[int]) -> pd.DataFrame:
    """月末エクスポージャを集める (確定済みの月末はキャッシュから)。

    Args:
        ctx: 実行コンテキスト。
        ends: 月末営業日のリスト。

    Returns:
        ``exp_date`` 列を持つ縦持ちの DataFrame。
    """
    settings = ctx.settings
    region_map = read_region_map(settings.resolve(settings.input.region_map))
    frames = []
    for exp_date in ends:
        cached = ctx.cache.get(KIND_NAM_EXPOSURE, exp_date)
        if cached is not None:
            frames.append(cached)
            continue
        ctx.log(f"NAM exposure: {exp_date}")
        df = _build_month_end_exposure(ctx, exp_date, region_map)
        ctx.cache.put(KIND_NAM_EXPOSURE, exp_date, df)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def run_nam(
    ctx: Context, from_ymd: int, to_ymd: int, *, cn: bool = False, q: int = 5
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """NAM ファクターの最上位分位ポートフォリオの日次リターン (D / S) を計算して保存する。

    ``archive/BLF.fret_nam_daily(from_ymd, to_ymd, CN, q)`` の置き換え。
    超過リターンはユニバース単純平均に対するもの。前回出力があれば増分計算する。

    Args:
        ctx: 実行コンテキスト。
        from_ymd: 開始日。
        to_ymd: 終了日。
        cn: ``True`` なら地域ごとに分位化する。
        q: 分位数。

    Returns:
        ``(D, S)``。D は列 ``date`` + ファクター列、S は列 ``dateym`` + ファクター列。
    """
    settings = ctx.settings
    calendar = business_days(settings.benchmark, NAM_CALENDAR_START_YMD, CALENDAR_END_YMD)
    ends = month_ends(calendar, drop_last=True)
    days = [d for d in calendar if from_ymd <= d <= to_ymd]

    ex_d = ctx.paths.latest_range_file(ctx.paths.factor_rtn_nam_dir("Drtn"), "", from_ymd, to_ymd)
    ex_s = ctx.paths.latest_range_file(ctx.paths.factor_rtn_nam_dir("Srtn"), "", from_ymd, to_ymd)
    existing_end = min(ex_d[1], ex_s[1]) if ex_d and ex_s else None
    plan = _plan(ctx, days, existing_end, to_ymd)
    kept_d = load_kept_rows(ex_d[0] if ex_d else None, "date", plan)
    kept_s = load_kept_rows(ex_s[0] if ex_s else None, "dateym", plan)

    new_d = pd.DataFrame(columns=["date"])
    new_s = pd.DataFrame(columns=["dateym"])
    if plan.compute_days:
        ends_series = pd.Series(ends)
        needed_ends = sorted(
            {
                int(ends_series[ends_series <= d].max())
                for d in plan.compute_days
                if (ends_series <= d).any()
            }
        )
        exposure = assign_quantiles(
            expand_month_end_exposures(
                month_end_exposures(ctx, needed_ends), plan.compute_days, ends
            ),
            q=q,
            columns=NAM_FACTORS,
            by_region=cn,
        )
        bids = exposure["bid"].unique().tolist()
        first, last = plan.compute_days[0], plan.compute_days[-1]

        ret = ret_global_daily(first, last, bids)
        ret["date"] = ret["date"].astype(str).str.replace("-", "").astype(int)
        ret = demean_by_date(ret, "date", "return_price_usd")

        sret = sret_global_daily(first, last, bids)
        sret["dateym"] = sret["dateym"].astype(int)
        sret = demean_by_date(sret, "dateym", "ret")

        new_d = top_quantile_returns(
            ret, exposure, date_col="date", value_col="return_price_usd", q=q
        ).reset_index()
        new_s = top_quantile_returns(
            sret, exposure, date_col="dateym", value_col="ret", q=q
        ).reset_index()

    d = merge_rows(kept_d, new_d, "date")
    s = merge_rows(kept_s, new_s, "dateym")

    d_path = ctx.paths.factor_rtn_nam("Drtn", from_ymd, to_ymd)
    d.to_csv(d_path, index=False)
    ctx.log(f"Save to {d_path}")
    s_path = ctx.paths.factor_rtn_nam("Srtn", from_ymd, to_ymd)
    s.to_csv(s_path, index=False)
    ctx.log(f"Save to {s_path}")
    return d, s


# ----------------------------------------------------------------------
# 読み込み・描画
# ----------------------------------------------------------------------
def load_common(ctx: Context, from_ymd: int, to_ymd: int) -> pd.DataFrame:
    """保存済みの共通ファクターリターン CSV を読む。"""
    return pd.read_csv(ctx.paths.factor_rtn_common(from_ymd, to_ymd))


def load_nam(ctx: Context, from_ymd: int, to_ymd: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """保存済みの NAM ファクターリターン CSV (D, S) を読む。"""
    return (
        pd.read_csv(ctx.paths.factor_rtn_nam("Drtn", from_ymd, to_ymd)),
        pd.read_csv(ctx.paths.factor_rtn_nam("Srtn", from_ymd, to_ymd)),
    )


def plot_all(
    ctx: Context,
    common: pd.DataFrame,
    nam_d: pd.DataFrame,
    nam_s: pd.DataFrame,
    factor_exp_common: pd.DataFrame,
    from_ymd: int,
) -> None:
    """ファクターリターン関連の 4 つの図を保存する。

    Args:
        ctx: 実行コンテキスト。
        common: ``run_common`` の出力。
        nam_d: ``run_nam`` の D。
        nam_s: ``run_nam`` の S。
        factor_exp_common: ``factor_exposure.run`` の出力。
        from_ymd: 強調区間の開始日 (週初)。
    """
    if not ctx.plot:
        return
    fig = plot_factor_exposure(
        common[common["ymd"] >= from_ymd], nam_d[nam_d["date"] >= from_ymd], factor_exp_common
    )
    ctx.save_figure(fig, "plot_factor_exp")
    ctx.save_figure(plot_common_factor_cumulative(common, from_ymd), "Common_factor_Drtn")
    ctx.save_figure(
        plot_nam_factor_cumulative(nam_d, "date", from_ymd, "NAM factor Drtn"), "NAM_factor_Drtn"
    )
    ctx.save_figure(
        plot_nam_factor_cumulative(nam_s, "dateym", from_ymd, "NAM factor Srtn"), "NAM_factor_Srtn"
    )
