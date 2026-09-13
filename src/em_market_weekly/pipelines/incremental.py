"""増分計算のヘルパー

日ごとに独立した値 (日次ファクターリターン、IC など) は、前回出力に新しい日を
追記すればよい。ただしデータは後から改訂されうるので、改訂ウィンドウ
(``settings.revision_window_days``) 以内の日付は毎回計算し直す。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from em_market_weekly.dates import shift_days


@dataclass(frozen=True)
class Plan:
    """増分計算の計画

    Attributes:
        cutoff: この日付以前 (含む) の既存行を保持する。``None`` なら全期間再計算。
        compute_days: 今回計算する日 (昇順)。
    """

    cutoff: int | None
    compute_days: list[int]

    @property
    def full(self) -> bool:
        """全期間再計算か。"""
        return self.cutoff is None


def make_plan(
    days: Sequence[int],
    existing_end: int | None,
    to_ymd: int,
    revision_window_days: int,
    *,
    recompute: bool = False,
) -> Plan:
    """保持する既存行と計算する日を決める。

    Args:
        days: 対象期間の営業日 (昇順)。
        existing_end: 前回出力の終了日。無ければ ``None``。
        to_ymd: 今回の終了日。
        revision_window_days: 改訂ウィンドウ (暦日)。
        recompute: ``True`` なら全期間再計算。

    Returns:
        計画。

    Examples:
        >>> days = [20260825, 20260826, 20260827, 20260828, 20260831, 20260901]
        >>> make_plan(days, existing_end=20260828, to_ymd=20260901, revision_window_days=3)
        Plan(cutoff=20260828, compute_days=[20260831, 20260901])
        >>> make_plan(days, existing_end=20260901, to_ymd=20260901, revision_window_days=3)
        Plan(cutoff=20260829, compute_days=[20260831, 20260901])
        >>> make_plan(days, None, 20260901, 3).full
        True
    """
    if recompute or existing_end is None:
        return Plan(None, list(days))
    cutoff = min(existing_end, shift_days(to_ymd, -revision_window_days))
    return Plan(cutoff, [d for d in days if d > cutoff])


def to_ymd_series(values: pd.Series) -> pd.Series:
    """日付らしき列 (``YYYYMMDD`` int / ISO 文字列 / date) を ``YYYYMMDD`` int に揃える。

    Args:
        values: 変換する列。

    Returns:
        int の Series。

    Examples:
        >>> to_ymd_series(pd.Series(["2026-09-01", "2026-09-02"])).tolist()
        [20260901, 20260902]
        >>> to_ymd_series(pd.Series([20260901])).tolist()
        [20260901]
    """
    if pd.api.types.is_integer_dtype(values):
        return values.astype(int)
    return pd.to_datetime(values).dt.strftime("%Y%m%d").astype(int)


def load_kept_rows(path: Path | None, date_col: str, plan: Plan) -> pd.DataFrame | None:
    """前回出力から ``cutoff`` 以前の行を読む。全期間再計算なら ``None``。

    Args:
        path: 前回出力の CSV。
        date_col: 日付列名。
        plan: 計画。

    Returns:
        保持する行、または ``None``。
    """
    if plan.full or path is None:
        return None
    df = pd.read_csv(path)
    return df[to_ymd_series(df[date_col]) <= plan.cutoff].reset_index(drop=True)


def merge_rows(kept: pd.DataFrame | None, new: pd.DataFrame, date_col: str) -> pd.DataFrame:
    """保持行と新規行を結合し、日付順に並べる。重複する日付は新規行を優先する。

    Args:
        kept: 保持する既存行 (``None`` 可)。
        new: 新規計算行。
        date_col: 日付列名。

    Returns:
        結合した DataFrame。

    Examples:
        >>> kept = pd.DataFrame({"d": [1, 2], "v": [1.0, 2.0]})
        >>> new = pd.DataFrame({"d": [2, 3], "v": [20.0, 30.0]})
        >>> merge_rows(kept, new, "d")["v"].tolist()
        [1.0, 20.0, 30.0]
    """
    frames = [f for f in (kept, new) if f is not None and not f.empty]
    if not frames:
        return new
    out = pd.concat(frames, ignore_index=True)
    key = to_ymd_series(out[date_col])
    out = out.assign(_key=key).drop_duplicates("_key", keep="last").sort_values("_key")
    return out.drop(columns="_key").reset_index(drop=True)
