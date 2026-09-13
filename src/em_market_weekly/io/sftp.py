"""itaap サーバー (SFTP) 上のファイル読み込み

``archive/common_function.itaap_read_file`` の移植。認証情報は環境変数から取り、
1 クライアントで接続を使い回す。「指定日以前で最新のファイルを探す」処理を
``read_latest_on_or_before`` に集約する (archive では 5 箇所に重複していた)。
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Literal, Self

import pandas as pd

from em_market_weekly.dates import shift_days
from em_market_weekly.settings import env_required

FileType = Literal["csv", "dat"]


@dataclass
class ItaapClient:
    """itaap への SFTP クライアント

    Attributes:
        host: ホスト名。
        username: ユーザー名。
        password: パスワード。
        port: ポート番号。
        home_prefix: リモートパスの先頭に付与するプレフィックス。
            archive では ``/abe/...`` のようにユーザー名から始まるパスを渡し、
            内部で ``/home`` を前置していた。

    Examples:
        >>> client = ItaapClient.from_env()  # doctest: +SKIP
        >>> df = client.read_csv("/abe/blf/score/daily/20260901.csv")  # doctest: +SKIP
        >>> client.close()  # doctest: +SKIP
    """

    host: str
    username: str
    password: str
    port: int = 22
    home_prefix: str = "/home"
    _ssh: object | None = field(default=None, init=False, repr=False)

    @classmethod
    def from_env(cls) -> ItaapClient:
        """環境変数 ``ITAAP_HOST`` / ``ITAAP_USERNAME`` / ``ITAAP_PASSWORD`` から生成する。

        Returns:
            クライアント。
        """
        return cls(
            host=env_required("ITAAP_HOST"),
            username=env_required("ITAAP_USERNAME"),
            password=env_required("ITAAP_PASSWORD"),
        )

    def _connect(self):
        import paramiko

        if self._ssh is None:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
            )
            self._ssh = ssh
        return self._ssh

    def close(self) -> None:
        """SSH 接続を閉じる。"""
        if self._ssh is not None:
            self._ssh.close()
            self._ssh = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def _open(self, remote_path: str) -> Iterator[object]:
        ssh = self._connect()
        full_path = f"{self.home_prefix}{remote_path}"
        with ssh.open_sftp() as sftp, sftp.open(full_path, "r", bufsize=32768) as f:
            yield f

    def read_csv(self, remote_path: str) -> pd.DataFrame:
        """リモートの CSV を読む。

        Args:
            remote_path: ``home_prefix`` を除いたリモートパス。

        Returns:
            読み込んだ DataFrame。

        Raises:
            OSError: ファイルが存在しない場合など。
        """
        with self._open(remote_path) as f:
            return pd.read_csv(f)

    def read_dat(self, remote_path: str) -> pd.DataFrame:
        """リモートのタブ区切り ``.dat`` をヘッダ無しで読む。

        Args:
            remote_path: ``home_prefix`` を除いたリモートパス。

        Returns:
            読み込んだ DataFrame (ヘッダ無し)。
        """
        with self._open(remote_path) as f:
            return pd.read_csv(f, sep="\t", header=None)

    def read(self, remote_path: str, file_type: FileType = "csv") -> pd.DataFrame:
        """種類を指定してリモートファイルを読む。

        Args:
            remote_path: リモートパス。
            file_type: ``"csv"`` または ``"dat"``。

        Returns:
            読み込んだ DataFrame。
        """
        if file_type == "csv":
            return self.read_csv(remote_path)
        if file_type == "dat":
            return self.read_dat(remote_path)
        raise ValueError(f"Unsupported file_type: {file_type!r}")

    def read_latest_on_or_before(
        self,
        path_for: Callable[[int], str],
        ymd: int,
        *,
        max_lookback: int | None = None,
        file_type: FileType = "csv",
    ) -> tuple[pd.DataFrame, int]:
        """``ymd`` から 1 日ずつ遡り、最初に見つかったファイルを読む。

        Args:
            path_for: ``YYYYMMDD`` からリモートパスを組み立てる関数。
            ymd: 探索開始日。
            max_lookback: 遡る最大日数。``None`` なら見つかるまで遡る
                (archive の ``while True`` と同じ。安全のため 3650 日で打ち切る)。
            file_type: ファイル種別。

        Returns:
            ``(DataFrame, 実際に読めた日付)`` のタプル。

        Raises:
            FileNotFoundError: 上限まで遡っても見つからない場合。

        Examples:
            >>> client.read_latest_on_or_before(  # doctest: +SKIP
            ...     lambda d: f"/abe/blf/score/daily/{d}.csv", 20260906
            ... )
            (<DataFrame>, 20260904)
        """
        limit = 3650 if max_lookback is None else max_lookback
        current = ymd
        for _ in range(limit + 1):
            path = path_for(current)
            try:
                return self.read(path, file_type), current
            except OSError:
                current = shift_days(current, -1)
        raise FileNotFoundError(
            f"No file found within {limit} days on or before {ymd} ({path_for(ymd)})."
        )
