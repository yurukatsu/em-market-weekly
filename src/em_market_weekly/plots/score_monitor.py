"""スコアモニター図 (IC / アクティブウェイト相関 / リバランス相関)"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from em_market_weekly.plots.style import recent_slice


def plot_score_monitor(
    ic: pd.DataFrame,
    reb_corr: pd.DataFrame,
    active_corr: pd.DataFrame,
    from_ymd: int,
    reb_ymd: int,
    score_type: str,
) -> Figure:
    """IC (棒 + 20 日移動平均)、アクティブウェイト相関 (線)、リバランス相関 (棒) を描く。

    ``archive/BLF.plot_Score_monitor`` の移植。

    Args:
        ic: 列 ``date``, ``c`` (``ic_by_date`` の CSV を読んだもの)。
        reb_corr: 列 ``dateymd``, ``c``。
        active_corr: 列 ``date`` (``YYYYMMDD``), ``Correlation``。
        from_ymd: 強調区間の開始日。
        reb_ymd: 凡例に表示するリバランス日。
        score_type: スコア種別 (ラベル用)。

    Returns:
        描画した Figure。
    """
    ic = ic.copy()
    ic["date"] = pd.to_datetime(ic["date"])
    ic = ic.dropna(subset=["c"]).reset_index(drop=True)
    ic["20BD_MA"] = ic["c"].rolling(window=20).mean()

    active_corr = active_corr.copy()
    active_corr["date"] = pd.to_datetime(active_corr["date"], format="%Y%m%d")
    reb_corr = reb_corr.copy()
    reb_corr["dateymd"] = pd.to_datetime(reb_corr["dateymd"], format="%Y%m%d")

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 12), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )

    # --- 上段: IC ---
    ax1.bar(ic["date"], ic["c"], label=f"IC {score_type}", color="blue", alpha=0.5, width=0.8)
    recent = recent_slice(ic, "date", from_ymd)
    ax1.bar(recent["date"].iloc[1:], recent["c"].iloc[1:], color="red", alpha=1.0, width=0.8)
    ax1.plot(ic["date"], ic["20BD_MA"], label="20BD Moving Average", color="darkblue", linewidth=2)

    ax1_twin = ax1.twinx()
    ax1_twin.plot(
        active_corr["date"],
        active_corr["Correlation"],
        label=f"Active vs {score_type} Correlation",
        color="purple",
        linewidth=2,
        linestyle="-",
    )
    ax1_twin.set_ylim(-0.5, 0.5)

    ax1.set_ylabel(f"IC {score_type}", fontsize=14)
    ax1.axhline(0, color="black", linewidth=1, linestyle="--", alpha=0.7)
    ax1.grid(alpha=0.3, axis="y")
    ax1.tick_params(axis="y", labelcolor="blue")
    ax1_twin.set_ylabel(f"Active vs {score_type} Correlation", fontsize=14, color="purple")
    ax1_twin.tick_params(axis="y", labelcolor="purple")

    for _, row in recent.iloc[1:].iterrows():
        y_offset = 0.02 if row["c"] >= 0 else -0.02
        ax1.text(
            row["date"],
            row["c"] + y_offset,
            f"{row['c']:.2f}",
            fontsize=10,
            ha="center",
            va="bottom" if row["c"] >= 0 else "top",
        )

    corr_recent = active_corr[active_corr["date"].isin(recent["date"])]
    if not corr_recent.empty:
        for row, offset, va in (
            (corr_recent.iloc[0], 0.01, "bottom"),
            (corr_recent.iloc[-1], -0.01, "top"),
        ):
            ax1_twin.plot(row["date"], row["Correlation"], marker="D", markersize=6, color="red")
            ax1_twin.text(
                row["date"],
                row["Correlation"] + offset,
                f"{row['Correlation']:.3f}",
                fontsize=10,
                ha="center",
                va=va,
                color="red",
            )

    # --- 下段: リバランス相関 ---
    ax2.bar(
        reb_corr["dateymd"],
        reb_corr["c"],
        label=f"Rebalance Correlation {score_type} ({reb_ymd})",
        color="orange",
        alpha=0.7,
        width=0.8,
    )
    reb_recent = reb_corr[reb_corr["dateymd"].isin(recent["date"])]
    if not reb_recent.empty:
        ax2.bar(
            reb_recent["dateymd"].iloc[1:],
            reb_recent["c"].iloc[1:],
            color="red",
            alpha=1.0,
            width=0.8,
        )
        for row in (reb_recent.iloc[0], reb_recent.iloc[-1]):
            ax2.text(
                row["dateymd"],
                row["c"] + 0.02,
                f"{row['c']:.3f}",
                fontsize=10,
                ha="center",
                va="bottom",
                color="red",
            )

    ax2.set_xlabel("Date", fontsize=14)
    ax2.set_ylabel("Rebalance Correlation", fontsize=14, color="orange")
    ax2.axhline(0, color="black", linewidth=1, linestyle="--", alpha=0.7)
    ax2.grid(alpha=0.3, axis="y")
    ax2.tick_params(axis="y", labelcolor="orange")

    ax1.legend(loc="upper left", fontsize=12)
    ax1_twin.legend(loc="upper right", fontsize=12)
    ax2.legend(loc="upper left", fontsize=12)
    fig.tight_layout()
    return fig
