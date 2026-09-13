"""RGA vs MSEM / MSAC 累積リターン図"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from em_market_weekly.dates import ymd_to_timestamp


def plot_index_return(
    rga: pd.DataFrame,
    msem: pd.DataFrame,
    msac: pd.DataFrame,
    diff: pd.DataFrame,
    from_ymd: int,
    to_ymd: int,
) -> Figure:
    """RGA / MSEM / MSAC の累積リターンと RGA−MSEM 累積差を描く。

    ノートブック内 ``RGA_Rtn_graph`` の描画部分。

    Args:
        rga: 列 ``Dates``, ``cumret`` (``tail_cumulative`` の出力)。
        msem: 同上。
        msac: 同上。
        diff: 列 ``Dates``, ``cumdiff`` (``cumulative_return_difference`` の出力)。
        from_ymd: 黄色背景の開始日。
        to_ymd: タイトルに表示する終了日。

    Returns:
        描画した Figure。
    """
    from_dt = ymd_to_timestamp(from_ymd)
    to_dt = ymd_to_timestamp(to_ymd)
    xmax = max(msem["Dates"].max(), msac["Dates"].max(), rga["Dates"].max())

    fig, ax = plt.subplots(figsize=(14, 9))
    ax.plot(rga["Dates"], rga["cumret"] * 100, color="#DD2C00", label="RGA", linewidth=2.2)
    ax.plot(msem["Dates"], msem["cumret"] * 100, color="#757575", label="MSEM", linewidth=2.2)
    ax.plot(msac["Dates"], msac["cumret"] * 100, color="#AED581", label="MSAC", linewidth=2.2)

    ax.fill_between(
        diff["Dates"],
        diff["cumdiff"],
        0,
        color="royalblue",
        step="mid",
        alpha=0.25,
        label="RGA-MSEM",
    )
    ax.plot(
        diff["Dates"],
        diff["cumdiff"],
        color="royalblue",
        linewidth=2,
        linestyle="--",
        label="RGA-MSEM",
    )

    ax.axvspan(from_dt, xmax, color="yellow", alpha=0.2, zorder=0)
    ax.spines["bottom"].set_linewidth(1.5)
    ax.axhline(0, color="black", linewidth=1.5, linestyle="-")
    ax.set_xlabel("Date", fontsize=13)
    ax.set_ylabel("B&H Return [%]", fontsize=13)
    ax.set_title(
        f"{from_dt.strftime('%Y-%m-%d')} to {to_dt.strftime('%Y-%m-%d')}",
        fontsize=15,
        weight="bold",
        pad=15,
    )
    ax.legend(loc="upper left", fontsize=12)
    fig.tight_layout()
    return fig
