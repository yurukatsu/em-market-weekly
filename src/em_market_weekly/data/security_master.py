"""銘柄コード変換 (fs_trfac_glb.public.barraid)"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

import pandas as pd

from em_market_weekly.dates import ymd_to_iso
from em_market_weekly.io.database import FsTrfacGlb, get_data

CodeFlag = Literal["sedol", "bid", "isin"]


def _quote_list(codes: Iterable[str]) -> str:
    return ",".join(f"'{c}'" for c in codes)


def code_change(ymd: int, codes: Iterable[str], flag: CodeFlag) -> pd.DataFrame:
    """指定コードに対応する bid / sedol / isin を取得する。

    ``archive/common_function.wd_code_change`` の移植。

    Args:
        ymd: 基準日 (``YYYYMMDD``)。
        codes: 検索するコードのリスト。
        flag: ``codes`` の種類 (``"sedol"`` / ``"bid"`` / ``"isin"``)。

    Returns:
        列 ``date``, ``bid``, ``sedol``, ``isin`` を持つ DataFrame。

    Raises:
        ValueError: ``flag`` が不正な場合。

    Examples:
        >>> code_change(20260901, ["B0JGGP5"], "sedol")  # doctest: +SKIP
    """
    if flag not in ("sedol", "bid", "isin"):
        raise ValueError(f"Unsupported flag: {flag!r}")
    sql = f"""
        SELECT date, RTRIM(bid) AS bid, RTRIM(sedol) AS sedol, RTRIM(isin) AS isin
        FROM public.barraid
        WHERE date = '{ymd}' AND {flag} IN ({_quote_list(codes)})
    """
    return get_data(sql, FsTrfacGlb)


def bid_to_namid(ymd: int, bids: Iterable[str]) -> pd.DataFrame:
    """bid → nam_id の対応表を取得する。

    ``archive/BLF.bid_to_namid`` の移植。

    Args:
        ymd: 基準日 (``YYYYMMDD``)。
        bids: bid のリスト。

    Returns:
        列 ``bid``, ``sedol``, ``nam_id`` を持つ DataFrame。
    """
    quoted = "', '".join(bids)
    sql = f"""
        SELECT a.bid, a.sedol, a.nam_id FROM public.barraid AS a
        WHERE a.bid IN ('{quoted}') AND a.date = '{ymd_to_iso(ymd)}'
    """
    df = get_data(sql, FsTrfacGlb)
    df["bid"] = df["bid"].str.strip()
    return df
