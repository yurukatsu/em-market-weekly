"""銘柄リターン (fs_trfac_glb.public.exshare / RISK_MODELS.GEM3_D_SRTN)"""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from em_market_weekly.data.security_master import bid_to_namid
from em_market_weekly.dates import ymd_to_iso
from em_market_weekly.io.database import FsTrfacGlb, RiskModels, get_data


def ret_usd(ymd: int, bids: Iterable[str]) -> pd.DataFrame:
    """1 日分の USD 建て価格リターンを取得する。

    ``archive/BLF.get_ret_usd`` の移植。

    Args:
        ymd: 基準日 (``YYYYMMDD``)。
        bids: bid のリスト。

    Returns:
        列 ``date``, ``nam_id``, ``return_price_usd``, ``bid``, ``sedol`` を持つ DataFrame。
    """
    return ret_global_daily(ymd, ymd, bids)


def ret_global_daily(from_ymd: int, to_ymd: int, bids: Iterable[str]) -> pd.DataFrame:
    """期間中の日次 USD 建て価格リターンを取得する。

    ``archive/BLF.get_ret_global_daily`` の移植。bid → nam_id の対応は
    ``from_ymd`` 時点のものを使う。

    Args:
        from_ymd: 開始日 (``YYYYMMDD``)。
        to_ymd: 終了日 (``YYYYMMDD``)。
        bids: bid のリスト。

    Returns:
        列 ``date``, ``nam_id``, ``return_price_usd``, ``bid``, ``sedol`` を持つ DataFrame。
    """
    ch = bid_to_namid(from_ymd, bids)
    namid = "', '".join(ch["nam_id"])
    sql = f"""
        SELECT a.date, a.nam_id, a.drtnp AS return_price_usd
        FROM public.exshare AS a
        WHERE a.nam_id IN ('{namid}')
          AND a.date >= '{ymd_to_iso(from_ymd)}' AND a.date <= '{ymd_to_iso(to_ymd)}'
    """
    df = get_data(sql, FsTrfacGlb)
    return df.merge(ch, on="nam_id", how="inner")


def sret_global_daily(from_ymd: int, to_ymd: int, bids: Iterable[str]) -> pd.DataFrame:
    """期間中の日次固有リターン (Barra GEM3 SRTN) を取得する。

    ``archive/BLF.get_sret_global_daily`` の移植。``|ret| >= 100`` の行は除外する。

    Args:
        from_ymd: 開始日 (``YYYYMMDD``)。
        to_ymd: 終了日 (``YYYYMMDD``)。
        bids: bid のリスト。

    Returns:
        列 ``dateym`` (実際は ``YYYYMMDD``), ``bid``, ``ret`` を持つ DataFrame。
    """
    quoted = "', '".join(bids)
    sql = f"""
        SELECT a.[DATE] AS dateym, RTRIM(a.BID) AS bid, a.SRTN AS ret
        FROM GEM3_D_SRTN AS a
        WHERE a.BID IN ('{quoted}') AND a.[DATE] >= '{from_ymd}' AND a.[DATE] <= '{to_ymd}'
    """
    df = get_data(sql, RiskModels)
    return df[df["ret"].abs() < 100]
