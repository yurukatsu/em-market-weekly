"""共通ファクター / NAM ファクターの期間リターンとアクティブウェイトの棒グラフ"""

from __future__ import annotations

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from matplotlib.figure import Figure

from em_market_weekly.constants import FACTOR_CATEGORIES


def plot_factor_exposure(
    factor_rtn_common: pd.DataFrame,
    factor_rtn_nam: pd.DataFrame,
    factor_exp_common: pd.DataFrame,
    cmap: str = "coolwarm",
    categories: dict[str, list[str]] | None = None,
) -> Figure:
    """期間中の共通ファクターリターン (カテゴリ平均) と NAM ファクター Q5 リターンを描く。

    ``archive/BLF.plot_factor_exp`` の移植。上段には
    ``Active Weighted Average`` を 10 倍にスケールして第二軸に重ねる。

    Args:
        factor_rtn_common: 列 ``ymd`` + ファクター列 (期間で絞り込み済み)。
        factor_rtn_nam: 列 ``date`` + NAM ファクター列 (期間で絞り込み済み)。
        factor_exp_common: 列 ``Category``, ``Active Weighted Average``。
        cmap: カラーマップ名。
        categories: カテゴリ辞書 (既定 ``FACTOR_CATEGORIES``)。

    Returns:
        描画した Figure。
    """
    categories = FACTOR_CATEGORIES if categories is None else categories
    from_ymd = factor_rtn_common["ymd"].min()
    to_ymd = factor_rtn_common["ymd"].max()

    column_sums = factor_rtn_common.drop(columns=["ymd"]).sum(axis=0)
    cat_sums = {
        cat: column_sums[[c for c in factors if c in column_sums.index]].mean()
        for cat, factors in categories.items()
        if any(c in column_sums.index for c in factors)
    }
    cat_df = (
        pd.DataFrame(list(cat_sums.items()), columns=["Category", "Sum"])
        .sort_values("Sum", ascending=False)
        .reset_index(drop=True)
    )

    nam_df = factor_rtn_nam.set_index("date").sum().reset_index()
    nam_df.columns = ["Variable", "Sum"]
    nam_df = nam_df.sort_values("Sum", ascending=False).reset_index(drop=True)

    exp = factor_exp_common.copy()
    exp["Scaled Active Weighted Average"] = exp["Active Weighted Average"] * 10
    merged = cat_df.merge(exp, on="Category", how="left")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 16), gridspec_kw={"height_ratios": [1.5, 1]})
    sns.set(style="whitegrid")

    max_abs = max(merged["Sum"].abs().max(), nam_df["Sum"].abs().max())
    norm = matplotlib.colors.TwoSlopeNorm(vmin=-max_abs, vcenter=0, vmax=max_abs)
    cmap_inst = matplotlib.colormaps[cmap].reversed()

    colors_top = [cmap_inst(norm(v)) for v in merged["Sum"]]
    sns.barplot(
        x="Sum", y="Category", data=merged, hue="Category", palette=colors_top, legend=False, ax=ax1
    )
    ax1.axvline(0, color="black", linewidth=0.8, linestyle="--")
    ax1.set_title(f"Common Factor return ({from_ymd} to {to_ymd})", fontsize=18)
    ax1.set_xlabel("return(%)", fontsize=16)
    ax1.set_ylabel("Category", fontsize=16)
    ax1.set_xlim(-max_abs, max_abs)
    for idx, row in merged.iterrows():
        ax1.text(
            row["Sum"],
            idx - 0.2,
            f"{row['Sum']:.2f}",
            color="black",
            va="center",
            ha="right" if row["Sum"] < 0 else "left",
        )

    ax1_twin = ax1.twiny()
    ax1_twin.scatter(
        merged["Scaled Active Weighted Average"],
        range(len(merged)),
        color="limegreen",
        s=100,
        label=f"Active Weight ({from_ymd})",
    )
    ax1_twin.set_xlim(ax1.get_xlim())
    for idx, row in merged.iterrows():
        x = row["Scaled Active Weighted Average"]
        ax1_twin.text(
            x,
            idx + 0.2,
            f"{row['Active Weighted Average']:.3f}",
            color="limegreen",
            va="center",
            ha="right" if x < 0 else "left",
        )
    ax1_twin.legend(loc="upper right")

    colors_bottom = [cmap_inst(norm(v)) for v in nam_df["Sum"]]
    sns.barplot(
        x="Sum",
        y="Variable",
        data=nam_df,
        hue="Variable",
        palette=colors_bottom,
        legend=False,
        ax=ax2,
    )
    ax2.axvline(0, color="black", linewidth=0.8, linestyle="--")
    ax2.set_title("Q5 Port Return", fontsize=18)
    ax2.set_xlabel("return(%)", fontsize=16)
    ax2.set_ylabel("NAM factor", fontsize=16)
    ax2.set_xlim(-max_abs, max_abs)
    for idx, row in nam_df.iterrows():
        ax2.text(
            row["Sum"],
            idx,
            f"{row['Sum']:.2f}",
            color="black",
            va="center",
            ha="right" if row["Sum"] < 0 else "left",
        )

    fig.tight_layout()
    return fig
