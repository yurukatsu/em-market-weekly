"""銘柄×スコアパネル (RGA ユニバース / 保有 / スコア / セクター の紐づけ)

``archive/BLF.RGA_universe_score`` の計算部分。DB アクセスは呼び出し側
(``pipelines.score_cumulative``) が行い、ここは DataFrame の結合のみを担う。
"""

from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd

from em_market_weekly.constants import UNIVERSE_SCORE_COLUMNS

SCORE_COLUMNS: list[str] = ["ai70_bd30", "ai", "bigdata"]

RENAME_MAP: dict[str, str] = {
    "bigdata": "BigData",
    "ai70_bd30": "AI70_BD30",
    "ai": "AI",
    "weight_BLF": "Port",
    "weight_RGA": "BM",
    "weight_ACT": "Active",
    "fac": "Sector",
    "rvl_z": "rvl",
    "TVL_z": "TVL",
    "NAMESG_z": "NAMESG",
    "culc_bigdata": "Calc_BD",
}


def prepare_universe(universe: pd.DataFrame, sedol_reverse: pd.Series) -> pd.DataFrame:
    """ユニバースに保有側 SEDOL (``sedol_chg``) 列を付与する。

    Args:
        universe: ``read_rga_universe`` の出力。
        sedol_reverse: ユニバース SEDOL → 保有 SEDOL の ``Series``。

    Returns:
        ``sedol_chg`` 列を加えた DataFrame (コピー)。
    """
    out = universe.copy()
    out["sedol_chg"] = out["sedol"].replace(sedol_reverse)
    return out


def link_rga_universe(universe: pd.DataFrame, rga: pd.DataFrame) -> pd.DataFrame:
    """ユニバースに RGA 構成ウェイトを紐づける。

    ``archive/BLF._link_RGA_universe`` の移植。SEDOL で外部結合し、
    ユニバースに無い RGA 銘柄は ``sedol_chg`` 経由で埋める。それでも無ければ行を追加する。

    Args:
        universe: ``prepare_universe`` の出力。
        rga: ``rga_bm_weight`` の出力。

    Returns:
        ``bid``, ``adjmktcap``, ``weight`` を加えた DataFrame。
    """
    merged = universe.merge(rga[["sedol", "bid", "adjmktcap", "weight"]], on="sedol", how="outer")
    nan_rows = merged[merged["English Name"].isna()]
    known = merged.dropna(subset=["English Name"])
    unmatched: list[pd.Series] = []

    for _, row in nan_rows.iterrows():
        idx = known[known["sedol_chg"] == row["sedol"]].index
        if not idx.empty:
            for i in idx:
                for col in ("bid", "adjmktcap", "weight"):
                    if pd.isna(known.at[i, col]):
                        known.at[i, col] = row[col]
        else:
            unmatched.append(row)

    if unmatched:
        known = pd.concat([known, pd.DataFrame(unmatched)], ignore_index=True)
    return known


def link_positions(universe: pd.DataFrame, holdings: pd.DataFrame) -> pd.DataFrame:
    """ユニバースに口座保有ウェイトを紐づける。

    ``archive/BLF._link_BLF_positions`` の移植。``sedol_chg`` と ``sedol`` の両方で
    結合して ``combine_first`` し、どちらにも無い保有銘柄は行として追加する。
    複数の SEDOL 候補から最頻値を ``sedol``、次点を ``sedol_sub`` とする。

    Args:
        universe: ``link_rga_universe`` の出力。
        holdings: ``account_hold_daily`` の出力 (列 ``sedol``, ``name``, ``weight``, ``country_code``)。

    Returns:
        ``Name``, ``Country``, ``weight_RGA``, ``weight_BLF``, ``sedol``, ``sedol_sub`` を持つ DataFrame。
    """
    h = holdings[["sedol", "name", "weight", "country_code"]]
    by_chg = universe.merge(
        h[["sedol", "name", "weight"]],
        left_on="sedol_chg",
        right_on="sedol",
        how="left",
        suffixes=("_RGA", "_BLF"),
    )
    by_sedol = universe.merge(
        h[["sedol", "name", "weight"]],
        left_on="sedol",
        right_on="sedol",
        how="left",
        suffixes=("_RGA", "_BLF"),
    )
    combined = by_chg.combine_first(by_sedol)

    all_sedols = set(combined["sedol"].dropna()).union(
        combined["sedol_BLF"].dropna(),
        combined["sedol_RGA"].dropna(),
        combined["sedol_chg"].dropna(),
    )
    extra = h[~h["sedol"].isin(all_sedols)].rename(
        columns={"weight": "weight_BLF", "sedol": "sedol_BLF"}
    )
    result = pd.concat(
        [combined, extra[["name", "sedol_BLF", "weight_BLF", "country_code"]]],
        ignore_index=True,
        sort=False,
    )

    result["Name"] = np.where(
        result["English Name"].notna(), result["English Name"], result["name"]
    )
    result["Country"] = np.where(result["region"].notna(), result["region"], result["country_code"])
    result = result.drop(columns=["English Name", "name", "region", "country_code"])

    sedol_cols = ["sedol", "sedol_BLF", "sedol_RGA", "sedol_chg"]
    counts = result[sedol_cols].apply(lambda row: Counter(row.dropna()), axis=1)
    result["sedol"] = counts.apply(lambda c: c.most_common(1)[0][0] if c else np.nan)
    result["sedol_sub"] = counts.apply(lambda c: c.most_common(2)[1][0] if len(c) > 1 else np.nan)
    return result.drop(columns=["sedol_BLF", "sedol_RGA", "sedol_chg"])


def add_active_weight(df: pd.DataFrame) -> pd.DataFrame:
    """``weight_ACT = weight_BLF - weight_RGA`` を付与する (NaN は 0)。

    Args:
        df: ``link_positions`` の出力。

    Returns:
        ``weight_ACT`` を加えた DataFrame (コピー)。
    """
    out = df.copy()
    out["weight_RGA"] = out["weight_RGA"].fillna(0)
    out["weight_BLF"] = out["weight_BLF"].fillna(0)
    out["weight_ACT"] = out["weight_BLF"] - out["weight_RGA"]
    return out


def link_ai_score(df: pd.DataFrame, score: pd.DataFrame) -> pd.DataFrame:
    """AI スコアを ``sedol`` で紐づけ、欠損は ``sedol_sub`` で補完する。

    ``archive/BLF._link_AI_score`` の移植。

    Args:
        df: ``add_active_weight`` の出力。
        score: 列 ``sedol``, ``ai70_bd30``, ``ai``, ``bigdata`` を持つスコア。

    Returns:
        スコア列を加えた DataFrame。
    """
    out = df.merge(score[["sedol", *SCORE_COLUMNS]], on="sedol", how="left")
    sub = score.rename(columns={"sedol": "sedol_sub"})
    additional = (
        out[out["ai70_bd30"].isna()]
        .drop(columns=SCORE_COLUMNS)
        .merge(sub[["sedol_sub", *SCORE_COLUMNS]], on="sedol_sub", how="left")
        .dropna(subset=SCORE_COLUMNS)
    )
    for _, row in additional.iterrows():
        for i in out[out["sedol_sub"] == row["sedol_sub"]].index:
            for col in SCORE_COLUMNS:
                if pd.isna(out.at[i, col]):
                    out.at[i, col] = row[col]
    return out


def attach_bid(df: pd.DataFrame, code_map: pd.DataFrame) -> pd.DataFrame:
    """``sedol`` から引いた bid で既存の ``bid`` を上書き補完する。

    ``archive/BLF._link_bid`` の移植。

    Args:
        df: ``bid`` 列を持つ DataFrame。
        code_map: 列 ``bid``, ``sedol`` を持つ対応表 (``code_change`` の出力)。

    Returns:
        ``bid`` を更新した DataFrame。
    """
    out = df.merge(code_map[["bid", "sedol"]], on="sedol", how="left", suffixes=("_x", "_y"))
    out["bid"] = np.where(out["bid_y"].notna(), out["bid_y"], out["bid_x"])
    return out.drop(columns=["bid_x", "bid_y"])


def attach_sector(df: pd.DataFrame, sector: pd.DataFrame) -> pd.DataFrame:
    """セクター名 (``fac``) を ``bid`` で紐づける。

    Args:
        df: ``bid`` 列を持つ DataFrame。
        sector: 列 ``bid``, ``fac`` (``gem3_sector`` の出力)。

    Returns:
        ``fac`` を加えた DataFrame。
    """
    return df.merge(sector[["bid", "fac"]], on="bid", how="left")


def attach_bigdata(df: pd.DataFrame, bigdata: pd.DataFrame) -> pd.DataFrame:
    """BigData z スコアを ``bid`` で紐づける。

    Args:
        df: ``bid`` 列を持つ DataFrame。
        bigdata: ``compute_bigdata_scores`` の出力。

    Returns:
        ``rvl_z``, ``TVL_z``, ``NAMESG_z``, ``culc_bigdata`` を加えた DataFrame。
    """
    cols = ["bid", "rvl_z", "TVL_z", "NAMESG_z", "culc_bigdata"]
    return df.merge(bigdata[cols], on="bid", how="left")


def finalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """列名を出力仕様に揃え、``UNIVERSE_SCORE_COLUMNS`` の順に並べる。

    Args:
        df: ``attach_bigdata`` までを適用した DataFrame。

    Returns:
        出力列のみを持つ DataFrame。
    """
    return df.rename(columns=RENAME_MAP)[UNIVERSE_SCORE_COLUMNS]
