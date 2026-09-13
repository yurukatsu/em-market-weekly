"""累積ファクターリターンの折れ線図 (共通ファクター / NAM ファクター)

archive の ``plot_Common_factor_Drtn`` / ``plot_NAM_factor_Drtn`` / ``plot_NAM_factor_Srtn``
を 2 関数に統合した。
"""

from __future__ import annotations

from collections.abc import Sequence

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

from em_market_weekly.constants import FACTOR_CATEGORIES, NAM_PLOT_FACTORS
from em_market_weekly.features.transforms import category_means
from em_market_weekly.plots.style import recent_slice

_TAB10 = matplotlib.colormaps["tab10"]
NAM_COLORS: dict[str, tuple[float, float, float, float]] = {
    "ai70_bd30": _TAB10(4),
    "ai": _TAB10(0),
    "TVL": _TAB10(3),
    "rvl": _TAB10(2),
}


def _annotate_ends(
    ax: plt.Axes,
    recent: pd.DataFrame,
    date_col: str,
    column: str,
    color: str | tuple | None,
    position: str = "auto",
) -> None:
    """強調区間の最初と最後の点に値ラベルを付ける。"""
    for i, (_, row) in enumerate(recent.iterrows()):
        if i not in (0, len(recent) - 1):
            continue
        if position == "down":
            y_offset, va = -0.1, "top"
        elif position == "up":
            y_offset, va = 0.1, "bottom"
        else:
            y_offset, va = (0.1, "bottom") if i == 0 else (-0.1, "top")
        ax.text(
            row[date_col],
            row[column] + y_offset,
            f"{row[column]:.2f}",
            fontsize=10,
            ha="center",
            va=va,
            color=color,
        )


def plot_common_factor_cumulative(
    factor_rtn: pd.DataFrame,
    from_ymd: int,
    categories: dict[str, list[str]] | None = None,
    title: str = "Common factor Drtn",
) -> Figure:
    """共通ファクター日次リターンをカテゴリ平均し、累積和を描く。

    ``archive/BLF.plot_Common_factor_Drtn`` の移植。

    Args:
        factor_rtn: 列 ``ymd`` (``YYYYMMDD``) + ファクター列。
        from_ymd: 強調区間の開始日。
        categories: カテゴリ辞書 (既定 ``FACTOR_CATEGORIES``)。
        title: タイトル。

    Returns:
        描画した Figure。
    """
    categories = FACTOR_CATEGORIES if categories is None else categories
    df = factor_rtn.copy()
    df["ymd"] = pd.to_datetime(df["ymd"], format="%Y%m%d")
    means = category_means(df, categories)
    cum = pd.concat([df[["ymd"]], means.cumsum()], axis=1).reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(14, 8))
    recent = recent_slice(cum, "ymd", from_ymd)
    for category in cum.columns[1:]:
        (line,) = ax.plot(cum["ymd"], cum[category], label=category, linewidth=2)
        ax.plot(
            [recent["ymd"].iloc[0], recent["ymd"].iloc[-1]],
            [recent[category].iloc[0], recent[category].iloc[-1]],
            marker="o",
            markersize=8,
            linestyle="None",
            color=line.get_color(),
        )
        _annotate_ends(ax, recent, "ymd", category, None)

    ax.set_title(title, fontsize=16)
    ax.set_xlabel("Date", fontsize=14)
    ax.set_ylabel("Cumulative Sum (%)", fontsize=14)
    ax.legend(title="Categories", fontsize=12, title_fontsize=14)
    ax.grid(alpha=0.3)
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig


def plot_nam_factor_cumulative(
    factor_rtn: pd.DataFrame,
    date_col: str,
    from_ymd: int,
    title: str,
    factors: Sequence[str] = NAM_PLOT_FACTORS,
) -> Figure:
    """NAM ファクターリターンの累積和を描く (先頭に 0 行を追加)。

    ``archive/BLF.plot_NAM_factor_Drtn`` / ``plot_NAM_factor_Srtn`` の移植。
    系列は最終値の昇順に描き、最終値が中央値未満ならラベルを下に付ける。

    Args:
        factor_rtn: ``date_col`` (``YYYYMMDD``) + ファクター列を持つ DataFrame。
        date_col: 日付列名 (``"date"`` または ``"dateym"``)。
        from_ymd: 強調区間の開始日。
        title: タイトル。
        factors: 描く系列 (これ以外の列は無視)。

    Returns:
        描画した Figure。
    """
    df = factor_rtn.copy()
    df[date_col] = pd.to_datetime(df[date_col], format="%Y%m%d")
    value_cols = [c for c in df.columns if c != date_col]
    cum = df[[date_col]].copy()
    for c in value_cols:
        cum[c] = df[c].cumsum()
    start = {date_col: cum[date_col].iloc[0] - pd.Timedelta(days=1), **{c: 0 for c in value_cols}}
    cum = pd.concat([pd.DataFrame([start]), cum], ignore_index=True)

    final = cum.iloc[-1][value_cols]
    ordered = [c for c in final.sort_values().index if c in factors]
    positions = {c: ("down" if final[c] < final.median() else "up") for c in ordered}

    fig, ax = plt.subplots(figsize=(14, 8))
    recent = recent_slice(cum, date_col, from_ymd)
    for column in ordered:
        color = NAM_COLORS.get(column)
        ax.plot(cum[date_col], cum[column], label=column, linewidth=2, alpha=0.3, color=color)
        ax.plot(recent[date_col], recent[column], marker="o", markersize=8, color=color, alpha=1.0)
        _annotate_ends(ax, recent, date_col, column, color, positions[column])

    ax.set_title(title, fontsize=16)
    ax.set_xlabel("Date", fontsize=14)
    ax.set_ylabel("Cumulative Sum (%)", fontsize=14)
    legend = ax.legend(title="Factors", fontsize=12, title_fontsize=14)
    for line in legend.get_lines():
        line.set_linewidth(3)
    ax.grid(alpha=0.3)
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    return fig
