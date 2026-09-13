"""日付ヘルパー (DB 不要な純粋関数)

日付は archive と同様に ``YYYYMMDD`` 形式の ``int`` を基本とし、
月は ``YYYYMM`` 形式の ``int`` で扱う。
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime

import pandas as pd
from dateutil.relativedelta import relativedelta


def ymd_to_date(ymd: int) -> date:
    """``YYYYMMDD`` 整数を ``datetime.date`` に変換する。

    Args:
        ymd: 日付を表す整数 (例: 20260901)。

    Returns:
        対応する ``date``。

    Examples:
        >>> ymd_to_date(20260901)
        datetime.date(2026, 9, 1)
    """
    return pd.to_datetime(str(ymd), format="%Y%m%d").date()


def date_to_ymd(d: date | datetime | pd.Timestamp) -> int:
    """日付を ``YYYYMMDD`` 整数に変換する。

    Args:
        d: 変換する日付。

    Returns:
        ``YYYYMMDD`` 整数。

    Examples:
        >>> date_to_ymd(date(2026, 9, 1))
        20260901
    """
    return int(pd.Timestamp(d).strftime("%Y%m%d"))


def ymd_to_iso(ymd: int) -> str:
    """``YYYYMMDD`` 整数を ``YYYY-MM-DD`` 文字列に変換する。

    Args:
        ymd: 日付を表す整数。

    Returns:
        ISO 形式の日付文字列。

    Examples:
        >>> ymd_to_iso(20260901)
        '2026-09-01'
    """
    s = str(ymd)
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def ymd_to_timestamp(ymd: int) -> pd.Timestamp:
    """``YYYYMMDD`` 整数を ``pd.Timestamp`` に変換する。

    Args:
        ymd: 日付を表す整数。

    Returns:
        対応する ``Timestamp``。
    """
    return pd.to_datetime(str(ymd), format="%Y%m%d")


def ymd_to_ym(ymd: int) -> int:
    """``YYYYMMDD`` から ``YYYYMM`` を取り出す。

    Args:
        ymd: 日付を表す整数。

    Returns:
        年月を表す整数。

    Examples:
        >>> ymd_to_ym(20260901)
        202609
    """
    return int(str(ymd)[:6])


def shift_month(ym: int, months: int) -> int:
    """``YYYYMM`` を指定月数だけずらす。

    archive の ``ai_alt_score.get_pym`` および ``monthly_calendar`` を使った
    「前月を求める」処理の置き換え。

    Args:
        ym: 基準となる年月 (例: 202609)。
        months: ずらす月数。負の値で過去。

    Returns:
        ずらした後の年月。

    Examples:
        >>> shift_month(202601, -1)
        202512
        >>> shift_month(202612, 1)
        202701
    """
    base = pd.to_datetime(str(ym), format="%Y%m")
    shifted = base + relativedelta(months=months)
    return int(shifted.strftime("%Y%m"))


def previous_month(ymd: int) -> int:
    """日付の属する月の前月を ``YYYYMM`` で返す。

    Args:
        ymd: 日付を表す整数。

    Returns:
        前月の年月。

    Examples:
        >>> previous_month(20260901)
        202608
    """
    return shift_month(ymd_to_ym(ymd), -1)


def shift_days(ymd: int, days: int) -> int:
    """``YYYYMMDD`` を暦日でずらす。

    Args:
        ymd: 日付を表す整数。
        days: ずらす日数。負の値で過去。

    Returns:
        ずらした後の日付。

    Examples:
        >>> shift_days(20260301, -1)
        20260228
    """
    return date_to_ymd(ymd_to_timestamp(ymd) + pd.Timedelta(days=days))


def nearest_on_or_before(candidates: Iterable[int], ymd: int) -> int:
    """候補日のうち ``ymd`` 以前で最も近い日付を返す。

    archive の ``BLF._create_calendar`` と同じ挙動。

    Args:
        candidates: 候補となる ``YYYYMMDD`` の列。
        ymd: 基準日。

    Returns:
        ``ymd`` 以前で最大の候補日。``ymd`` 自身が候補に含まれていればそれ。

    Raises:
        ValueError: ``ymd`` 以前の候補日が存在しない場合。

    Examples:
        >>> nearest_on_or_before([20260828, 20260831, 20260901], 20260830)
        20260828
    """
    earlier = [d for d in candidates if d <= ymd]
    if not earlier:
        raise ValueError(f"No candidate date on or before {ymd}.")
    return max(earlier)


def month_ends(dates: Iterable[int], drop_last: bool = True) -> list[int]:
    """営業日リストから各月の最終営業日を抽出する。

    Args:
        dates: ``YYYYMMDD`` の営業日列。
        drop_last: ``True`` の場合、末尾の月 (進行中で不完全な可能性がある月) を除く。

    Returns:
        月末営業日のリスト (昇順)。

    Examples:
        >>> month_ends([20260129, 20260130, 20260227, 20260302], drop_last=False)
        [20260130, 20260227, 20260302]
        >>> month_ends([20260129, 20260130, 20260227, 20260302])
        [20260130, 20260227]
    """
    s = pd.Series(sorted(set(dates)))
    ends = s.groupby(s // 100).max().tolist()
    return ends[:-1] if drop_last else ends
