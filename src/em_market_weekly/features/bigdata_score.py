"""BigData 合成スコア (rvl / TVL / NAMESG)"""

from __future__ import annotations

import numpy as np
import pandas as pd

from em_market_weekly.constants import BIGDATA_CLIP, BIGDATA_WEIGHTS
from em_market_weekly.features.transforms import zscore_omit


def composite_score(row: pd.Series, weights: dict[str, float]) -> float:
    """z スコアの加重和。全て NaN なら NaN、一部 NaN は 0 扱い。

    Args:
        row: ``{factor}_z`` 列を持つ 1 行。
        weights: ファクター名 → ウェイト。

    Returns:
        合成スコア。
    """
    values = {f: row[f"{f}_z"] for f in weights}
    if all(np.isnan(v) for v in values.values()):
        return np.nan
    return sum(w * (0.0 if np.isnan(values[f]) else values[f]) for f, w in weights.items())


def compute_bigdata_scores(
    df: pd.DataFrame,
    weights: dict[str, float] | None = None,
    clip: float = BIGDATA_CLIP,
) -> pd.DataFrame:
    """rvl / TVL / NAMESG から BigData 合成スコアを計算する。

    ``archive/BLF._calculate_bigdata_scores`` の移植。
    各ファクターを z スコア化し、加重和を再度 z スコア化して ``±clip`` に丸める。

    Args:
        df: 列 ``bid``, ``rvl``, ``TVL``, ``NAMESG`` を持つ DataFrame。
        weights: ファクター名 → ウェイト (既定は ``BIGDATA_WEIGHTS``)。
        clip: クリップ幅。

    Returns:
        入力に ``rvl_z``, ``TVL_z``, ``NAMESG_z``, ``composite_score``,
        ``culc_bigdata`` を加えた DataFrame (コピー)。

    Examples:
        >>> df = pd.DataFrame({"bid": list("abc"), "rvl": [1, 2, 3],
        ...                    "TVL": [3, 2, 1], "NAMESG": [1, 1, 2]})
        >>> compute_bigdata_scores(df)["culc_bigdata"].round(2).tolist()
        [-0.71, -0.71, 1.41]
    """
    weights = BIGDATA_WEIGHTS if weights is None else weights
    out = df.copy()
    for f in weights:
        out[f"{f}_z"] = zscore_omit(out[f])
    out["composite_score"] = out.apply(composite_score, axis=1, weights=weights)
    out["culc_bigdata"] = zscore_omit(out["composite_score"]).clip(lower=-clip, upper=clip)
    return out
