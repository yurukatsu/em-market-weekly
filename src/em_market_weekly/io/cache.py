"""日付キーのローカルファイルキャッシュ

SFTP 上のスコアファイルや月末エクスポージャなど「日付ごとに 1 つ」のデータを
ローカルに保存し、2 回目以降の取得を省く。データは後から改訂されうるので、
``revision_window_days`` 以内の日付は信頼せず毎回取り直す。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd

from em_market_weekly.dates import date_to_ymd, shift_days


@dataclass
class FileCache:
    """日付キーの DataFrame キャッシュ

    Attributes:
        directory: キャッシュのルートディレクトリ。
        revision_window_days: 改訂ウィンドウ (暦日)。``today - window`` より後の日付は
            キャッシュに保存も参照もしない。
        refresh: ``True`` なら参照せず常に取り直す (保存はする)。
        today: 基準日 (テスト用に差し替え可能)。

    Examples:
        >>> cache = FileCache(Path("/tmp/c"), revision_window_days=10, today=20260914)
        >>> cache.is_final(20260901), cache.is_final(20260910)
        (True, False)
    """

    directory: Path
    revision_window_days: int = 10
    refresh: bool = False
    today: int = field(default_factory=lambda: date_to_ymd(date.today()))  # noqa: DTZ011

    @property
    def final_cutoff(self) -> int:
        """この日付以前 (含む) はキャッシュを信頼する。"""
        return shift_days(self.today, -self.revision_window_days)

    def is_final(self, ymd: int) -> bool:
        """``ymd`` のデータが改訂ウィンドウの外 (確定済み扱い) か。"""
        return ymd <= self.final_cutoff

    def _path(self, kind: str, key: int | str) -> Path:
        return self.directory / kind / f"{key}.pkl"

    def _missing_path(self, kind: str, key: int | str) -> Path:
        return self.directory / kind / f"{key}.missing"

    def get(self, kind: str, key: int, ymd: int | None = None) -> pd.DataFrame | None:
        """キャッシュを読む。無い、または信頼できない場合は ``None``。

        Args:
            kind: 種別 (サブディレクトリ名)。
            key: キー (通常は ``YYYYMMDD`` または ``YYYYMM``)。
            ymd: 鮮度判定に使う日付。``None`` なら ``key`` を使う。

        Returns:
            キャッシュされた DataFrame または ``None``。
        """
        if self.refresh or not self.is_final(key if ymd is None else ymd):
            return None
        path = self._path(kind, key)
        return pd.read_pickle(path) if path.exists() else None

    def put(self, kind: str, key: int, df: pd.DataFrame, ymd: int | None = None) -> None:
        """確定済み扱いの日付ならキャッシュに保存する。

        Args:
            kind: 種別。
            key: キー。
            df: 保存する DataFrame。
            ymd: 鮮度判定に使う日付。``None`` なら ``key`` を使う。
        """
        if not self.is_final(key if ymd is None else ymd):
            return
        path = self._path(kind, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_pickle(path)
        self._missing_path(kind, key).unlink(missing_ok=True)

    def is_missing(self, kind: str, key: int) -> bool:
        """「存在しない」と記録済みか (確定済み日付のみ有効)。"""
        if self.refresh or not self.is_final(key):
            return False
        return self._missing_path(kind, key).exists()

    def mark_missing(self, kind: str, key: int) -> None:
        """確定済み扱いの日付について「存在しない」と記録する。"""
        if not self.is_final(key):
            return
        path = self._missing_path(kind, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
