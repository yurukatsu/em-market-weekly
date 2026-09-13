"""ローカルの入力ファイル (RGA ユニバース / SEDOL 変換表 / 地域マップ)"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

UNIVERSE_COLUMNS: list[str] = ["English Name", "isin", "sedol", "region", "Exchange"]


def read_rga_universe(path: Path) -> pd.DataFrame:
    """RGA ユニバースの xlsx を読む。

    Args:
        path: xlsx のパス。

    Returns:
        列 ``English Name``, ``isin``, ``sedol``, ``region``, ``Exchange`` を持つ DataFrame。
    """
    return pd.read_excel(path)[UNIVERSE_COLUMNS]


def read_sedol_map(path: Path) -> pd.DataFrame:
    """SEDOL 変換表 (保有銘柄 → ユニバース) を読む。

    Args:
        path: xlsx のパス (列 ``変換FROM``, ``変換TO``)。

    Returns:
        列 ``from_sedol``, ``to_sedol`` を持つ DataFrame。
    """
    df = pd.read_excel(path)
    return df.rename(columns={"変換FROM": "from_sedol", "変換TO": "to_sedol"})[
        ["from_sedol", "to_sedol"]
    ]


def sedol_forward_map(sedol_map: pd.DataFrame) -> pd.Series:
    """保有銘柄 SEDOL → ユニバース SEDOL の ``Series`` (``replace`` 用)。"""
    return sedol_map.set_index("from_sedol")["to_sedol"]


def sedol_reverse_map(sedol_map: pd.DataFrame) -> pd.Series:
    """ユニバース SEDOL → 保有銘柄 SEDOL の ``Series`` (``replace`` 用)。"""
    return sedol_map.set_index("to_sedol")["from_sedol"]


def read_region_map(path: Path) -> pd.DataFrame:
    """国コード → 地域の xlsx を読む。列名は小文字化する。

    Args:
        path: xlsx のパス。

    Returns:
        列 ``ctry``, ``cname``, ``region`` を持つ DataFrame。
    """
    df = pd.read_excel(path)
    df.columns = [c.lower() for c in df.columns]
    return df
