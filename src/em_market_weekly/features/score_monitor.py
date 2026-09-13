"""スコアモニター (IC / リバランス相関 / アクティブウェイト相関)"""

from __future__ import annotations

import pandas as pd
from scipy.stats import pearsonr


def _pearson(x: pd.Series, y: pd.Series) -> float:
    return float(pearsonr(x, y)[0])


def ic_by_date(ret: pd.DataFrame, score_first: pd.DataFrame) -> pd.DataFrame:
    """初日のスコアと各日のリターンの相関 (IC) を日付ごとに求める。

    ``archive/BLF.score_IC_Reb`` の IC 部分。

    Args:
        ret: 列 ``date``, ``bid``, ``return_price_usd`` を持つ DataFrame。
        score_first: 列 ``bid``, ``value`` を持つ初日スコア。

    Returns:
        index=``date``, 列 ``c`` (相関) の DataFrame。
    """
    merged = ret.merge(score_first[["bid", "value"]], on="bid").dropna()
    return merged.groupby("date").apply(
        lambda g: pd.Series({"c": _pearson(g["return_price_usd"], g["value"])})
    )


def rebalance_corr(score: pd.DataFrame, reb_ymd: int) -> pd.DataFrame:
    """リバランス日のスコアと各日のスコアの相関を求める。

    ``archive/BLF.score_IC_Reb`` のリバランス相関部分。

    Args:
        score: 列 ``dateymd``, ``bid``, ``value`` を持つ日次スコア。
        reb_ymd: リバランス日 (``score`` に存在する日付)。

    Returns:
        index=``dateymd`` (``reb_ymd`` 以降), 列 ``c`` の DataFrame。
    """
    base = score.loc[score["dateymd"] == reb_ymd, ["bid", "value"]]
    merged = base.merge(score[score["dateymd"] >= reb_ymd], on="bid").dropna()
    return merged.groupby("dateymd").apply(
        lambda g: pd.Series({"c": _pearson(g["value_x"], g["value_y"])})
    )


def active_weight_corr(panel: pd.DataFrame, score_col: str, from_ymd: int) -> pd.DataFrame:
    """日付ごとにアクティブウェイトとスコアの相関を求める (``Active == 0`` は除外)。

    ``archive/BLF.ActiveWeight_score_Corr`` の計算部分。

    Args:
        panel: 列 ``date``, ``Active``, ``score_col`` を持つ累積パネル。
        score_col: スコア列名 (``AI`` / ``BigData`` / ``AI70_BD30``)。
        from_ymd: この日付以降のみ返す。

    Returns:
        列 ``date``, ``Correlation`` の DataFrame。

    Examples:
        >>> panel = pd.DataFrame({"date": [1, 1, 1, 2, 2, 2], "Active": [1, 2, 3, 1, 2, 3],
        ...                       "AI": [1, 2, 3, 3, 2, 1]})
        >>> active_weight_corr(panel, "AI", 1)["Correlation"].round(3).tolist()
        [1.0, -1.0]
    """
    df = panel[["date", "Active", score_col]].dropna()
    df = df[df["Active"] != 0]
    corr = (
        df.groupby("date")[["Active", score_col]]
        .corr()
        .iloc[0::2, -1]
        .reset_index()
        .rename(columns={score_col: "Correlation"})
        .drop(columns=["level_1"])
    )
    return corr[corr["date"] >= from_ymd].reset_index(drop=True)
