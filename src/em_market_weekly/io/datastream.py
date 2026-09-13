"""LSEG Datastream からの時系列取得

``DatastreamPy`` は会社環境でのみ利用するため関数内で遅延 import する。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from em_market_weekly.settings import env_required


@dataclass
class DatastreamClient:
    """Datastream クライアント

    Attributes:
        username: Datastream ユーザー名。
        password: Datastream パスワード。

    Examples:
        >>> ds = DatastreamClient.from_env()  # doctest: +SKIP
        >>> ds.price_series("MSEMKF$", 20210101, 20260901)  # doctest: +SKIP
    """

    username: str
    password: str
    _client: object | None = field(default=None, init=False, repr=False)

    @classmethod
    def from_env(cls) -> DatastreamClient:
        """環境変数 ``DS_USERNAME`` / ``DS_PASSWORD`` から生成する。

        Returns:
            クライアント。
        """
        return cls(username=env_required("DS_USERNAME"), password=env_required("DS_PASSWORD"))

    def _connect(self):
        import DatastreamPy as dsweb

        if self._client is None:
            self._client = dsweb.DataClient(None, self.username, self.password)
        return self._client

    def price_series(
        self,
        ticker: str,
        start_ymd: int,
        end_ymd: int,
        field_name: str = "MSPI",
        freq: str = "D",
    ) -> pd.DataFrame:
        """指数の価格系列を取得し、日次リターンを付与して返す。

        Args:
            ticker: Datastream ティッカー (例: ``"MSEMKF$"``)。
            start_ymd: 取得開始日 (``YYYYMMDD``)。
            end_ymd: 取得終了日 (``YYYYMMDD``)。
            field_name: 取得フィールド (既定 ``MSPI``)。
            freq: 頻度 (既定 日次)。

        Returns:
            列 ``Dates`` (datetime), ``Price``, ``Rtn`` (前日比) を持つ DataFrame。
        """
        ds = self._connect()
        raw = ds.get_data(
            tickers=ticker,
            fields=[field_name],
            kind=1,
            start=start_ymd,
            end=end_ymd,
            freq=freq,
        )
        prices = pd.Series(raw.values.flatten(), index=raw.index, dtype="float64")
        return pd.DataFrame(
            {
                "Dates": pd.to_datetime(prices.index),
                "Price": prices.values,
                "Rtn": prices.pct_change().values,
            }
        ).reset_index(drop=True)
