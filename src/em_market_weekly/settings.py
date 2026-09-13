"""設定の読み込み

パス・口座コードなどの非秘密情報は YAML から、認証情報は環境変数から読む。
出力先ディレクトリは YAML の ``base_dir`` を CLI から上書きできる。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = Path("config/settings.yaml")


class InputPaths(BaseModel):
    """入力ファイルのパス (``base_dir`` からの相対パス、または絶対パス)

    Attributes:
        rga_universe: RGA ユニバースの xlsx。
        sedol_map: SEDOL 変換表の xlsx (列: ``変換FROM``, ``変換TO``)。
        region_map: 国コード → 地域の xlsx (列: ``ctry``, ``cname``, ``region``)。
    """

    rga_universe: Path
    sedol_map: Path
    region_map: Path


class SftpPaths(BaseModel):
    """itaap サーバー上のディレクトリ

    Attributes:
        score_dir: AI スコア日次ファイル ``{ymd}.csv`` の置き場。
        bigdata_dir: BigData 日次ファイル ``{ymd}.csv`` の置き場。
        qip_dir: QIP 月次ファイル ``{ym}.dat`` の置き場。
    """

    score_dir: str
    bigdata_dir: str
    qip_dir: str


class AccountRule(BaseModel):
    """口座コードの適用ルール

    Attributes:
        cd: 口座コード。
        until: この日付 (``YYYYMMDD``) 以前に適用する。``None`` は無期限。
    """

    cd: str
    until: int | None = None


class Settings(BaseModel):
    """アプリケーション設定

    Attributes:
        base_dir: 入出力のベースディレクトリ。
        input: 入力ファイルパス。
        output_dir: CSV 出力先 (``base_dir`` 相対または絶対)。
        graph_dir: 図の出力先 (``base_dir`` 相対または絶対)。
        sftp: itaap 上のパス。
        accounts: 口座コードのルール (``until`` 昇順に評価する)。
        benchmark: 営業日カレンダーの基準指数。
        bigdata_min_ymd: BigData ファイルが存在する最古日。
            見つからない場合のフォールバック先。
        cache_dir: SFTP ファイルなどのローカルキャッシュ先 (``base_dir`` 相対または絶対)。
        revision_window_days: 改訂ウィンドウ (暦日)。この日数以内の日付のデータは
            「まだ改訂されうる」とみなし、キャッシュを信頼せず、増分計算でも再計算する。

    Examples:
        >>> s = Settings.load(Path("config/settings.yaml"))  # doctest: +SKIP
        >>> s.resolve(s.input.rga_universe)  # doctest: +SKIP
        PosixPath('/home_efs/BLF/input/RGA_universe/....xlsx')
    """

    base_dir: Path
    input: InputPaths
    output_dir: Path = Path("output")
    graph_dir: Path = Path("latest_graph")
    sftp: SftpPaths
    accounts: list[AccountRule] = Field(default_factory=list)
    benchmark: str = "MSEM"
    bigdata_min_ymd: int = 20260201
    cache_dir: Path = Path("cache")
    revision_window_days: int = 10

    @classmethod
    def load(
        cls,
        path: Path | str = DEFAULT_CONFIG_PATH,
        overrides: dict[str, Any] | None = None,
    ) -> Settings:
        """YAML から設定を読み込む。

        Args:
            path: YAML ファイルのパス。
            overrides: YAML の値を上書きする辞書 (トップレベルキーのみ)。
                ``None`` の値は無視する。

        Returns:
            読み込んだ設定。
        """
        with open(path, encoding="utf-8") as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}
        for key, value in (overrides or {}).items():
            if value is not None:
                raw[key] = value
        return cls.model_validate(raw)

    def resolve(self, path: Path | str) -> Path:
        """相対パスを ``base_dir`` 基準の絶対パスにする。

        Args:
            path: 相対または絶対パス。

        Returns:
            絶対パス。絶対パスが渡された場合はそのまま返す。
        """
        p = Path(path)
        return p if p.is_absolute() else self.base_dir / p

    def account_cd(self, ymd: int) -> str:
        """日付に対応する口座コードを返す。

        Args:
            ymd: 基準日 (``YYYYMMDD``)。

        Returns:
            口座コード。

        Raises:
            ValueError: 該当するルールが無い場合。
        """
        for rule in sorted(self.accounts, key=lambda r: (r.until is None, r.until or 0)):
            if rule.until is None or ymd <= rule.until:
                return rule.cd
        raise ValueError(f"No account rule matches {ymd}.")


def env_required(key: str) -> str:
    """必須の環境変数を読む。

    Args:
        key: 環境変数名。

    Returns:
        環境変数の値。

    Raises:
        KeyError: 未設定の場合。
    """
    try:
        return os.environ[key]
    except KeyError as exc:
        raise KeyError(f"Environment variable {key!r} is required.") from exc
