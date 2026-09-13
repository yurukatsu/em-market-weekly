"""汎用の変換 (順位正規化・z スコア・カテゴリ平均)"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm, zscore


def blom_score(x: pd.Series, alpha: float = 0.375) -> pd.Series:
    """Blom の順位正規化 (順位 → 正規分位点)。

    ``(rank - alpha) / (n - 2 * alpha + 1)`` を ``norm.ppf`` に通す。
    archive の ``BLF`` 内 ``(rk - 3/8) / (n + 1/4)`` と
    ``ai_alt_score.calc_blom_score`` は ``alpha = 0.375`` で一致する。

    Args:
        x: 変換する値。NaN は NaN のまま (``n`` には含む)。
        alpha: 補正係数。

    Returns:
        正規化後の値 (``x`` と同じ index)。

    Examples:
        >>> blom_score(pd.Series([1.0, 2.0, 3.0])).round(3).tolist()
        [-0.869, 0.0, 0.869]
    """
    rk = x.rank(method="average")
    rk_normed = (rk - alpha) / (len(rk) - 2 * alpha + 1)
    return pd.Series(norm.ppf(rk_normed), index=x.index, name=x.name)


def blom_score_by(df: pd.DataFrame, value_col: str, group_col: str) -> pd.Series:
    """グループごとに ``blom_score`` を適用する。

    Args:
        df: 対象データ。
        value_col: 値の列名。
        group_col: グループの列名。

    Returns:
        正規化後の値 (``df`` と同じ index)。
    """
    return df.groupby(group_col)[value_col].transform(blom_score)


def zscore_omit(x: pd.Series) -> pd.Series:
    """NaN を無視した z スコア。

    Args:
        x: 変換する値。

    Returns:
        z スコア (``x`` と同じ index)。NaN は NaN のまま。

    Examples:
        >>> zscore_omit(pd.Series([1.0, 2.0, 3.0])).round(3).tolist()
        [-1.225, 0.0, 1.225]
    """
    return pd.Series(zscore(x, nan_policy="omit"), index=x.index, name=x.name)


def category_means(df: pd.DataFrame, categories: dict[str, list[str]]) -> pd.DataFrame:
    """ファクター列をカテゴリごとに行方向平均する。

    Args:
        df: ファクター列を持つ DataFrame。
        categories: カテゴリ名 → ファクター列名のリスト。

    Returns:
        カテゴリ名を列とする DataFrame (``df`` と同じ index)。
        該当列が 1 つも無いカテゴリは含めない。

    Examples:
        >>> df = pd.DataFrame({"A1": [1.0, 2.0], "A2": [3.0, 4.0], "B1": [5.0, 6.0]})
        >>> category_means(df, {"A": ["A1", "A2"], "B": ["B1"], "C": ["X"]})
             A    B
        0  2.0  5.0
        1  3.0  6.0
    """
    out = pd.DataFrame(index=df.index)
    for category, factors in categories.items():
        valid = [f for f in factors if f in df.columns]
        if valid:
            out[category] = df[valid].mean(axis=1)
    return out


def quantile_labels(x: pd.Series, q: int) -> pd.Series:
    """値を ``q`` 分位に分け、1 始まりのラベルを返す (小さい方が 1)。

    ``pd.qcut(..., duplicates="drop")`` を使い、失敗時は全て NaN を返す。

    Args:
        x: 分位化する値。
        q: 分位数。

    Returns:
        1..q のラベル (float, NaN あり)。

    Examples:
        >>> quantile_labels(pd.Series([1, 2, 3, 4, 5]), 5).tolist()
        [1, 2, 3, 4, 5]
    """
    try:
        return pd.qcut(x, q, labels=False, duplicates="drop") + 1
    except (ValueError, IndexError):
        return pd.Series(np.nan, index=x.index, name=x.name)
