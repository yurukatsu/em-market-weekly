"""営業日カレンダー (equity.index_global ベース)"""

from __future__ import annotations

import numpy as np
import pandas as pd

from em_market_weekly.io.database import Equity, get_data


def bm_calendar(bm: str, from_ymd: int, to_ymd: int) -> pd.DataFrame:
    """指数の営業日カレンダーを取得する。

    ``archive/common_function.bm_calendar`` の移植。

    Args:
        bm: 指数コード (例: ``"MSEM"``, ``"MSUS"``)。
        from_ymd: 開始日 (``YYYYMMDD``)。
        to_ymd: 終了日 (``YYYYMMDD``)。

    Returns:
        列 ``dateymd`` (int), ``Date`` (datetime), ``yyyymm`` (int),
        ``eom`` (月末営業日なら 1) を持つ DataFrame。昇順。

    Examples:
        >>> bm_calendar("MSEM", 20260801, 20260831)["dateymd"].tolist()  # doctest: +SKIP
        [20260803, 20260804, ...]
    """
    sql = f"""
        SELECT DISTINCT dateymd
        FROM   index_global ind
        WHERE  ind.dateymd >= {from_ymd} AND ind.dateymd <= {to_ymd}
               AND ind.index_code = '{bm}'
    """
    df = get_data(sql, Equity).sort_values("dateymd").reset_index(drop=True)
    df["Date"] = pd.to_datetime(df["dateymd"], format="%Y%m%d")
    df["yyyymm"] = np.round(df["dateymd"] / 100, 0).astype(int)
    df["eom"] = 1 * ((df["yyyymm"].diff(-1)) != 0)
    return df


def business_days(bm: str, from_ymd: int, to_ymd: int) -> list[int]:
    """営業日を ``YYYYMMDD`` のリストで返す。

    Args:
        bm: 指数コード。
        from_ymd: 開始日。
        to_ymd: 終了日。

    Returns:
        昇順の営業日リスト。
    """
    return bm_calendar(bm, from_ymd, to_ymd)["dateymd"].tolist()
