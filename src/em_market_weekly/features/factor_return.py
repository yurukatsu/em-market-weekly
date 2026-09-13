"""共通ファクターの日次リターン (クロスセクション回帰)"""

from __future__ import annotations

import pandas as pd

from em_market_weekly.features.transforms import blom_score_by


def daily_factor_returns(ret: pd.DataFrame, exposure: pd.DataFrame) -> pd.Series:
    """1 日分のファクターリターンを単回帰の傾きとして求める。

    ``archive/BLF.fret_em_daily`` のループ内計算。エクスポージャは
    (すでに正規化済みでも) 再度 Blom 順位正規化してから回帰する (archive と同じ)。
    傾きは ``cov(s, r) / var(s)`` で求める (``LinearRegression`` と同値)。

    Args:
        ret: 列 ``bid``, ``return_price_usd`` を持つ DataFrame。
        exposure: 列 ``bid`` + ファクター列を持つ DataFrame (``normalize_exposures`` の出力を ``reset_index`` したもの)。

    Returns:
        index=ファクター名, values=回帰係数 の ``Series``。観測が 2 未満のファクターは NaN。

    Examples:
        >>> ret = pd.DataFrame({"bid": list("abcd"), "return_price_usd": [1.0, 2.0, 3.0, 4.0]})
        >>> exp = pd.DataFrame({"bid": list("abcd"), "F1": [1.0, 2.0, 3.0, 4.0]})
        >>> daily_factor_returns(ret, exp).round(3)["F1"] > 0
        True
    """
    data = ret[["bid", "return_price_usd"]].merge(exposure, on="bid", how="inner")
    data = data.melt(id_vars=["bid", "return_price_usd"])
    data = data[(data["return_price_usd"].abs() < 100) & (data["value"] > -100)].dropna()
    data["s"] = blom_score_by(data, "value", "variable")

    def slope(g: pd.DataFrame) -> float:
        if len(g) <= 1:
            return float("nan")
        x = g["s"]
        y = g["return_price_usd"]
        var = ((x - x.mean()) ** 2).sum()
        if var == 0:
            return float("nan")
        return float(((x - x.mean()) * (y - y.mean())).sum() / var)

    return data.groupby("variable").apply(slope).rename("coef")
