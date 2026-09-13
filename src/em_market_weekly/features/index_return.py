"""指数の累積リターンと差分 (RGA vs MSEM / MSAC)"""

from __future__ import annotations

import pandas as pd


def tail_cumulative(df: pd.DataFrame, price_col: str, window: int) -> pd.DataFrame:
    """末尾 ``window`` 行を取り、先頭を基準にした累積リターン ``cumret`` を付ける。

    Args:
        df: ``Dates`` 列と ``price_col`` を持つ DataFrame。
        price_col: 価格列名。
        window: 取り出す行数。

    Returns:
        ``Dates`` 昇順・末尾 ``window`` 行に ``cumret`` を加えた DataFrame。

    Examples:
        >>> df = pd.DataFrame({"Dates": pd.date_range("2026-01-01", periods=3), "P": [1.0, 1.1, 1.21]})
        >>> tail_cumulative(df, "P", 2)["cumret"].round(2).tolist()
        [0.0, 0.1]
    """
    out = df.sort_values("Dates").iloc[-window:].reset_index(drop=True).copy()
    out["cumret"] = out[price_col] / out[price_col].iloc[0] - 1
    return out


def cumulative_return_difference(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """2 系列の日次リターン差の累積 (%) を求める。

    Args:
        a: 列 ``Dates``, ``Rtn`` を持つ DataFrame (例: RGA)。
        b: 列 ``Dates``, ``Rtn`` を持つ DataFrame (例: MSEM)。

    Returns:
        列 ``Dates``, ``Rtn_a``, ``Rtn_b``, ``diff``, ``cumdiff`` (%) の DataFrame。
    """
    merged = a[["Dates", "Rtn"]].merge(
        b[["Dates", "Rtn"]], on="Dates", how="inner", suffixes=("_a", "_b")
    )
    merged["diff"] = merged["Rtn_a"] - merged["Rtn_b"]
    merged["cumdiff"] = merged["diff"].cumsum() * 100
    return merged
