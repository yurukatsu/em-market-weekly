"""描画の共通ヘルパー"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from em_market_weekly.dates import ymd_to_timestamp


def recent_slice(df: pd.DataFrame, date_col: str, from_ymd: int) -> pd.DataFrame:
    """``from_ymd`` の 1 営業日前から末尾までを切り出す。

    archive の各 plot 関数で「直近期間を強調表示する」ために使っていたロジック。
    ``from_ymd`` より前の行が無い場合は先頭から返す。

    Args:
        df: 日付列 (datetime) を持ち、日付昇順に並んだ DataFrame。
        date_col: 日付列名。
        from_ymd: 強調開始日 (``YYYYMMDD``)。

    Returns:
        切り出した DataFrame (index は保持)。
    """
    before = df[df[date_col] < ymd_to_timestamp(from_ymd)]
    if before.empty:
        return df
    start_pos = df.index.get_loc(before.index[-1])
    return df.iloc[start_pos:]


def close_all() -> None:
    """開いている Figure を全て閉じる (メモリ解放用)。"""
    plt.close("all")
