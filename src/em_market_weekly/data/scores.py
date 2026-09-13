"""itaap 上のスコアファイル (AI スコア / BigData / QIP)

``ScoreStore`` がローカルキャッシュ (``FileCache``) と SFTP を束ねる。
確定済み (改訂ウィンドウ外) の日付はキャッシュから読み、SFTP 接続は必要になるまで開かない。
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from em_market_weekly.dates import shift_days
from em_market_weekly.io.cache import FileCache
from em_market_weekly.io.sftp import ItaapClient
from em_market_weekly.settings import Settings

BIGDATA_COLUMNS: dict[str, str] = {"tvl": "TVL", "rvl": "rvl", "nam": "NAMESG"}

KIND_AI = "score_daily"
KIND_BIGDATA = "bigdata_daily"
KIND_QIP = "qip_monthly"


class ScoreStore:
    """スコアファイルの取得 (キャッシュ優先、無ければ SFTP)

    Args:
        settings: 設定 (``sftp.*`` を使う)。
        cache: ローカルキャッシュ。
        client_factory: SFTP クライアントを生成する関数 (必要になるまで呼ばない)。

    Examples:
        >>> store = ScoreStore(settings, cache, ItaapClient.from_env)  # doctest: +SKIP
        >>> df, found = store.ai_score_daily(20260901)  # doctest: +SKIP
    """

    def __init__(
        self,
        settings: Settings,
        cache: FileCache,
        client_factory: Callable[[], ItaapClient],
    ) -> None:
        self._settings = settings
        self._cache = cache
        self._client_factory = client_factory
        self._client: ItaapClient | None = None

    @property
    def client(self) -> ItaapClient:
        """SFTP クライアント (初回アクセス時に生成)"""
        if self._client is None:
            self._client = self._client_factory()
        return self._client

    def close(self) -> None:
        """SFTP 接続を閉じる。"""
        if self._client is not None:
            self._client.close()
            self._client = None

    # ------------------------------------------------------------------
    def _read_daily(
        self, kind: str, remote_path: Callable[[int], str], ymd: int
    ) -> pd.DataFrame | None:
        """1 日分を読む。キャッシュ → SFTP の順。存在しなければ ``None``。"""
        if self._cache.is_missing(kind, ymd):
            return None
        cached = self._cache.get(kind, ymd)
        if cached is not None:
            return cached
        try:
            df = self.client.read_csv(remote_path(ymd))
        except OSError:
            self._cache.mark_missing(kind, ymd)
            return None
        self._cache.put(kind, ymd, df)
        return df

    def _read_latest(
        self, kind: str, remote_path: Callable[[int], str], ymd: int, max_lookback: int | None
    ) -> tuple[pd.DataFrame, int]:
        limit = 3650 if max_lookback is None else max_lookback
        current = ymd
        for _ in range(limit + 1):
            df = self._read_daily(kind, remote_path, current)
            if df is not None:
                return df, current
            current = shift_days(current, -1)
        raise FileNotFoundError(
            f"No {kind} file within {limit} days on or before {ymd} ({remote_path(ymd)})."
        )

    # ------------------------------------------------------------------
    def ai_score_daily(self, ymd: int) -> tuple[pd.DataFrame, int]:
        """``ymd`` 以前で最新の AI スコア日次ファイルを読む。

        Args:
            ymd: 基準日 (``YYYYMMDD``)。

        Returns:
            ``(DataFrame, 実際に読めた日付)``。DataFrame は少なくとも
            ``bid``, ``ai``, ``bigdata``, ``ai70_bd30`` 列を持つ。
        """
        return self._read_latest(
            KIND_AI, lambda d: f"{self._settings.sftp.score_dir}/{d}.csv", ymd, None
        )

    def bigdata_daily(
        self, ymd: int, *, max_lookback: int = 9, fallback_ymd: int | None = None
    ) -> tuple[pd.DataFrame, int]:
        """``ymd`` 以前で最新の BigData 日次ファイル (tvl / rvl / nam) を読む。

        ``archive/BLF._get_bigdata_factors`` の移植。archive は 10 回 (当日 + 9 日) 遡っていた。

        Args:
            ymd: 基準日 (``YYYYMMDD``)。
            max_lookback: 遡る最大日数。
            fallback_ymd: 見つからない場合に読む日付。``None`` なら例外を送出する。

        Returns:
            ``(DataFrame, 実際に読めた日付)``。列は ``bid``, ``TVL``, ``rvl``, ``NAMESG``。

        Raises:
            FileNotFoundError: 見つからず ``fallback_ymd`` も無い場合。
        """

        def path_for(d: int) -> str:
            return f"{self._settings.sftp.bigdata_dir}/{d}.csv"

        try:
            df, found = self._read_latest(KIND_BIGDATA, path_for, ymd, max_lookback)
        except FileNotFoundError:
            if fallback_ymd is None:
                raise
            df = self._read_daily(KIND_BIGDATA, path_for, fallback_ymd)
            if df is None:
                raise
            found = fallback_ymd
        df = df[["bid", *BIGDATA_COLUMNS]].rename(columns=BIGDATA_COLUMNS)
        return df, found

    def qip_monthly(self, ym: int) -> pd.DataFrame:
        """QIP (特許) 月次ファイルを読み、数値列を変換して返す。

        ``archive/BLF.fret_nam_daily`` 内の QIP 読み込み部分。キャッシュの鮮度判定には
        月末日を使う。

        Args:
            ym: 年月 (``YYYYMM``)。

        Returns:
            1 行目をヘッダとした DataFrame。``invention_count_12m``, ``tassets``,
            ``sales`` は数値化済み。
        """
        month_end = int(pd.Period(str(ym), freq="M").end_time.strftime("%Y%m%d"))
        cached = self._cache.get(KIND_QIP, ym, ymd=month_end)
        if cached is not None:
            return cached
        raw = self.client.read_dat(f"{self._settings.sftp.qip_dir}/{ym}.dat")
        raw.columns = raw.iloc[0]
        df = raw[1:].reset_index(drop=True)
        for col in ("invention_count_12m", "tassets", "sales"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        self._cache.put(KIND_QIP, ym, df, ymd=month_end)
        return df
