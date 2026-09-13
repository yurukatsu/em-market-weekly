"""ポートフォリオ / ベンチマークの共通ファクターエクスポージャ (カテゴリ平均)"""

from __future__ import annotations

import pandas as pd

from em_market_weekly.constants import FACTOR_CATEGORIES, FACTOR_LIST
from em_market_weekly.features.transforms import blom_score_by


def normalize_exposures(exposure: pd.DataFrame) -> pd.DataFrame:
    """ファクター生値を銘柄横断で Blom 順位正規化し、bid × ファクターのワイド形式にする。

    ``archive/BLF.exp_em`` の変換部分。``value <= -100`` (欠損コード) は除外し、
    ピボット後の欠損は 0 で埋める。

    Args:
        exposure: 列 ``bid`` + ファクター列を持つ DataFrame (``date`` 列は不要)。

    Returns:
        index=``bid``, columns=ファクター名 の DataFrame。

    Examples:
        >>> df = pd.DataFrame({"bid": list("abc"), "F1": [1.0, 2.0, 3.0]})
        >>> normalize_exposures(df).round(3)  # doctest: +NORMALIZE_WHITESPACE
        variable     F1
        bid
        a        -0.869
        b         0.000
        c         0.869
    """
    long = exposure.drop(columns=["date"], errors="ignore").melt(id_vars=["bid"])
    long = long[long["value"] > -100].dropna()
    long["s"] = blom_score_by(long, "value", "variable")
    return long.pivot(index="bid", columns="variable", values="s").fillna(0)


def weighted_category_averages(
    df: pd.DataFrame,
    factor_list: list[str] | None = None,
    categories: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """BM / Port ウェイト加重のファクター値をカテゴリ平均する。

    ``archive/BLF.port_fct_exp`` の計算部分。各ファクターについて
    ``factor * BM`` と ``factor * Port`` の列平均を取り、カテゴリ内で平均する。

    Args:
        df: ``BM``, ``Port`` 列とファクター列を持つ DataFrame。
        factor_list: 対象ファクター (既定 ``FACTOR_LIST``)。
        categories: カテゴリ辞書 (既定 ``FACTOR_CATEGORIES``)。

    Returns:
        列 ``Category``, ``BM Weighted Average``, ``Port Weighted Average``,
        ``Active Weighted Average`` を持つ DataFrame。

    Examples:
        >>> df = pd.DataFrame({"BM": [1.0, 1.0], "Port": [2.0, 0.0], "F1": [1.0, 3.0]})
        >>> weighted_category_averages(df, ["F1"], {"Cat": ["F1"]})
          Category  BM Weighted Average  Port Weighted Average  Active Weighted Average
        0      Cat                  2.0                    1.0                     -1.0
    """
    factor_list = FACTOR_LIST if factor_list is None else factor_list
    categories = FACTOR_CATEGORIES if categories is None else categories
    present = [f for f in factor_list if f in df.columns]

    bm_avg: dict[str, float] = {}
    port_avg: dict[str, float] = {}
    for category, factors in categories.items():
        cols = [f for f in factors if f in present]
        if not cols:
            continue
        bm_avg[category] = (df[cols].mul(df["BM"], axis=0)).mean().mean()
        port_avg[category] = (df[cols].mul(df["Port"], axis=0)).mean().mean()

    out = pd.DataFrame(
        {
            "Category": list(bm_avg),
            "BM Weighted Average": list(bm_avg.values()),
            "Port Weighted Average": [port_avg[c] for c in bm_avg],
        }
    )
    out["Active Weighted Average"] = out["Port Weighted Average"] - out["BM Weighted Average"]
    return out
