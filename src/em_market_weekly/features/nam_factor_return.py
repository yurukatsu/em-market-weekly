"""NAM ファクター (AI / TVL / rvl / QIP) の分位ポートフォリオリターン"""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from em_market_weekly.constants import NAM_FACTORS
from em_market_weekly.features.transforms import quantile_labels


def expand_month_end_exposures(
    month_end_exposures: pd.DataFrame, business_days: Sequence[int], month_ends: Sequence[int]
) -> pd.DataFrame:
    """月末エクスポージャを各営業日に展開する (直近の月末値を使う)。

    Args:
        month_end_exposures: ``exp_date`` 列 (月末 ``YYYYMMDD``) を持つ DataFrame。
        business_days: 展開先の営業日。
        month_ends: 月末営業日の候補。

    Returns:
        ``exp_date`` を営業日に置き換えて縦に連結した DataFrame。
        直近月末が存在しない営業日は含まれない。

    Examples:
        >>> me = pd.DataFrame({"exp_date": [20260130, 20260227], "bid": ["a", "a"], "ai": [1, 2]})
        >>> expand_month_end_exposures(me, [20260202, 20260302], [20260130, 20260227])
           exp_date bid  ai
        0  20260202   a   1
        1  20260302   a   2
    """
    ends = pd.Series(sorted(month_ends))
    frames = []
    for d in business_days:
        prior = ends[ends <= d]
        if prior.empty:
            continue
        tmp = month_end_exposures[month_end_exposures["exp_date"] == prior.max()].copy()
        tmp["exp_date"] = d
        frames.append(tmp)
    if not frames:
        return month_end_exposures.iloc[0:0].copy()
    return pd.concat(frames, ignore_index=True)


def assign_quantiles(
    exposure: pd.DataFrame,
    q: int = 5,
    columns: Sequence[str] = NAM_FACTORS,
    by_region: bool = False,
) -> pd.DataFrame:
    """各ファクターを分位化し ``{col}_q`` 列を付ける。

    Args:
        exposure: ファクター列 (と ``by_region`` なら ``region`` 列) を持つ DataFrame。
        q: 分位数。
        columns: 分位化する列。
        by_region: ``True`` なら ``region`` ごとに分位化する (archive の ``CN=True``)。

    Returns:
        ``{col}_q`` 列を加えた DataFrame (コピー)。
    """
    out = exposure.copy()
    for col in columns:
        if by_region:
            out[f"{col}_q"] = out.groupby("region")[col].transform(quantile_labels, q=q)
        else:
            out[f"{col}_q"] = quantile_labels(out[col], q)
    return out


def demean_by_date(ret: pd.DataFrame, date_col: str, value_col: str) -> pd.DataFrame:
    """日付ごとの単純平均を差し引く (ユニバース等ウェイト超過リターン)。

    Args:
        ret: リターン DataFrame。
        date_col: 日付列名。
        value_col: リターン列名。

    Returns:
        ``value_col`` を超過リターンに置き換えた DataFrame (コピー)。

    Examples:
        >>> df = pd.DataFrame({"d": [1, 1, 2], "r": [1.0, 3.0, 5.0]})
        >>> demean_by_date(df, "d", "r")["r"].tolist()
        [-1.0, 1.0, 0.0]
    """
    out = ret.copy()
    out[value_col] = out[value_col] - out.groupby(date_col)[value_col].transform("mean")
    return out


def top_quantile_returns(
    ret: pd.DataFrame,
    exposure_q: pd.DataFrame,
    *,
    date_col: str,
    value_col: str,
    q: int = 5,
    columns: Sequence[str] = NAM_FACTORS,
) -> pd.DataFrame:
    """各ファクターの最上位分位ポートフォリオの日次平均リターンを求める。

    Args:
        ret: 列 ``bid``, ``date_col``, ``value_col`` を持つリターン (超過リターン)。
        exposure_q: 列 ``bid``, ``exp_date``, ``{col}_q`` を持つ分位ラベル。
        date_col: ``ret`` の日付列名。
        value_col: ``ret`` のリターン列名。
        q: 最上位とみなす分位ラベル。
        columns: 対象ファクター。

    Returns:
        index=日付, columns=ファクター名 のワイド DataFrame。
    """
    q_cols = [f"{c}_q" for c in columns]
    data = (
        ret[[date_col, value_col, "bid"]]
        .merge(
            exposure_q[["exp_date", "bid", *q_cols]],
            left_on=["bid", date_col],
            right_on=["bid", "exp_date"],
            how="left",
        )
        .melt(id_vars=[date_col, "bid", value_col, "exp_date"])
        .dropna()
    )
    data = data[(data[value_col].abs() < 100) & (data["value"] > -100)]
    data = data[data["value"] == q]
    wide = (
        data.groupby([date_col, "variable"])[value_col]
        .mean()
        .reset_index()
        .pivot(index=date_col, columns="variable", values=value_col)
    )
    wide.columns = [c.replace("_q", "") for c in wide.columns]
    return wide
