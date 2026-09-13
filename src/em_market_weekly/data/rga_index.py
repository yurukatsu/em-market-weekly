"""RGA 指数 (TRC.dbo.SGX_*) の構成銘柄・終値"""

from __future__ import annotations

import pandas as pd

from em_market_weekly.constants import RGA_INDEX_SYMBOL
from em_market_weekly.data.security_master import code_change
from em_market_weekly.io.database import TRC, get_data


def rga_calendar() -> list[int]:
    """RGA 指数の構成データが存在する日付を全て返す。

    ``archive/BLF._create_calendar`` の SQL 部分。

    Returns:
        ``YYYYMMDD`` のリスト (昇順)。
    """
    sql = f"""
        SELECT DISTINCT calc_date
        FROM TRC.dbo.SGX_Constituent
        WHERE Index_Symbol = '{RGA_INDEX_SYMBOL}' AND [SOD/EOD] = 'EOD'
    """
    return sorted(get_data(sql, TRC)["calc_date"].astype(int).unique().tolist())


def rga_bm_weight(ymd: int, sedol_map: pd.Series | None = None) -> pd.DataFrame:
    """RGA 指数の構成銘柄ウェイトを取得する。

    ``archive/BLF.RGA_BM_weight`` の移植。

    Args:
        ymd: 基準日 (``YYYYMMDD``)。
        sedol_map: 保有銘柄 SEDOL → ユニバース SEDOL の変換表
            (index=変換元, values=変換先)。``None`` なら変換しない。

    Returns:
        列 ``yyyymmdd``, ``date``, ``name``, ``sedol``, ``isin``, ``bid``,
        ``adjmktcap``, ``weight`` (%) を持つ DataFrame。ウェイト降順。

    Raises:
        AssertionError: bid 付与で行数が変わった場合。
    """
    sql = f"""
        SELECT a.calc_date AS yyyymmdd, a.SEDOL_Code AS sedol, a.ISIN_Code AS isin,
               a.Constituent_Name AS name, a.Adjusted_Market_Capitalisation AS adjmktcap,
               a.Index_Weight AS weight
        FROM TRC.dbo.SGX_Constituent a
        WHERE a.calc_date = {ymd}
          AND a.Index_Symbol = '{RGA_INDEX_SYMBOL}'
          AND a.[SOD/EOD] = 'EOD'
    """
    df = get_data(sql, TRC).sort_values(by="weight", ascending=False)
    n_rows = len(df)

    df["weight"] = df["weight"].apply(lambda x: float(x) * 100)
    df = df.reset_index(drop=True)
    df["sedol"] = df["sedol"].apply(lambda x: x.strip() if isinstance(x, str) else x)

    df = df.merge(code_change(ymd, df["sedol"], "sedol"), on=["sedol", "isin"], how="left")
    assert len(df) == n_rows, "The number of rows has changed while attaching bid."

    df = df[["yyyymmdd", "date", "name", "sedol", "isin", "bid", "adjmktcap", "weight"]]
    if sedol_map is not None:
        df["sedol"] = df["sedol"].replace(sedol_map)
    return df


def rga_index_close(to_ymd: int, from_ymd: int | None = None) -> pd.DataFrame:
    """RGA 指数の EOD 終値系列を取得する。

    ノートブック内 ``RGA_Rtn_graph`` の SQL 部分。

    Args:
        to_ymd: 取得終了日 (``YYYYMMDD``)。
        from_ymd: 取得開始日。``None`` なら全期間。

    Returns:
        列 ``Dates`` (datetime), ``Close``, ``Rtn`` (前日比) を持つ DataFrame。昇順。
    """
    sql = f"""
        SELECT [SOD/EOD], Index_Symbol, calc_date, [Close]
        FROM TRC.dbo.SGX_Index_Summary
        WHERE Index_Symbol = '{RGA_INDEX_SYMBOL}' AND [SOD/EOD] = 'EOD'
          AND calc_date <= {to_ymd}
          {f"AND calc_date >= {from_ymd}" if from_ymd is not None else ""}
        ORDER BY calc_date
    """
    df = get_data(sql, TRC)
    df["Rtn"] = df["Close"].pct_change()
    df["Dates"] = pd.to_datetime(df["calc_date"].astype(str))
    return df[["Dates", "Close", "Rtn"]]
