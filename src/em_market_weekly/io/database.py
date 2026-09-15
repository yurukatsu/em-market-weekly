"""社内データベースへの接続

``archive/sql_connect_new.py`` を移植し、本プロジェクトで必要な接続先
(TRC / GLOBAL / K_GX / factor_glb) を追加したもの。
``pylabcore`` は会社環境にしか無いため、関数内で遅延 import する。
"""

from __future__ import annotations

import os
from abc import ABC
from typing import ClassVar

import pandas as pd


class DatabaseError(Exception):
    """データベース処理に関する例外"""


class DatabaseNotConfiguredError(DatabaseError):
    """データベース接続情報が登録されていない場合の例外"""


class BaseDatabase(ABC):
    """データベース接続設定の基底クラス

    サブクラスでは、接続先を識別するためのクラス属性を定義する必要がある。
    ユーザー名とパスワードは、初期化時の引数または環境変数から取得する。

    Attributes:
        symbol_name: pylabcore で使用するデータベースの識別名。
        server_type: データベースサーバーの種類。
        server_address: データベースサーバーのアドレス。
        db_name: 接続先のデータベース名。
        charset: 接続に使用する文字コード。
        username_env_key: ユーザー名を取得する環境変数名。
        password_env_key: パスワードを取得する環境変数名。
        user_name: データベース接続に使用するユーザー名。
        user_passwd: データベース接続に使用するパスワード。
    """

    symbol_name: ClassVar[str]
    server_type: ClassVar[str]
    server_address: ClassVar[str]
    db_name: ClassVar[str]
    charset: ClassVar[str]
    username_env_key: ClassVar[str]
    password_env_key: ClassVar[str]
    user_name: ClassVar[str | None] = None
    user_passwd: ClassVar[str | None] = None

    @classmethod
    def set_db_info(
        cls,
        user_name: str | None = None,
        user_passwd: str | None = None,
    ) -> None:
        """pylabcore にデータベース接続情報を登録する。

        Args:
            user_name: ユーザー名。``None`` なら環境変数から取得する。
            user_passwd: パスワード。``None`` なら環境変数から取得する。

        Raises:
            ValueError: ユーザー名またはパスワードが得られない場合。
        """
        from pylabcore.database import set_db_info

        cls.user_name = user_name or os.getenv(cls.username_env_key)
        cls.user_passwd = user_passwd or os.getenv(cls.password_env_key)

        if cls.user_name is None:
            raise ValueError(f"user_name is required (env: {cls.username_env_key})")
        if cls.user_passwd is None:
            raise ValueError(f"user_passwd is required (env: {cls.password_env_key})")

        set_db_info(
            cls.symbol_name,
            cls.server_type,
            cls.server_address,
            cls.db_name,
            cls.user_name,
            cls.user_passwd,
            cls.charset,
        )

    @classmethod
    def check_connection(cls) -> None:
        """データベースへの接続を確認する (疎通テスト用)。

        接続情報を登録してから ``SELECT 1`` を実行する。
        通常のクエリ実行 (``get_data``) では呼ばない。

        Raises:
            DatabaseNotConfiguredError: ``symbol_name`` に対応する接続情報が
                pylabcore に登録されていない場合。
        """
        from pylabcore.database import execute_sql

        cls.set_db_info()
        try:
            execute_sql("SELECT 1;", cls.symbol_name)
        except KeyError as exc:
            raise DatabaseNotConfiguredError(
                f"Database information for {cls.symbol_name!r} is not configured."
            ) from exc


def get_data(
    sql: str,
    database: type[BaseDatabase],
    *,
    params: dict[str, str] | None = None,
    strip_strings: bool = True,
    user_name: str | None = None,
    user_passwd: str | None = None,
) -> pd.DataFrame:
    """指定した SQL を実行し、取得結果を DataFrame として返す。

    pylabcore の接続情報はグローバルな辞書に保持されており、``set_db_info`` の
    呼び出しで他の接続先の情報が失われることがある。そのため「登録済みかを確認して
    未登録なら登録する」のではなく、実行直前に必ず対象 DB の接続情報を登録し直す。
    登録は辞書への代入だけで接続は行わないので、毎回呼んでもコストはない。

    Args:
        sql: 実行する SQL。
        database: 接続先を表す ``BaseDatabase`` のサブクラス。
        params: SQL に渡すパラメータ。
        strip_strings: ``True`` なら文字列セルの前後空白を除去する
            (archive の ``sql_connect.get_sql`` と同じ挙動)。
        user_name: ユーザー名 (環境変数より優先)。
        user_passwd: パスワード (環境変数より優先)。

    Returns:
        取得結果。

    Examples:
        >>> from em_market_weekly.io.database import TRC, get_data
        >>> get_data("SELECT TOP 1 * FROM TRC.dbo.SGX_Constituent", TRC)  # doctest: +SKIP
    """
    from pylabcore.database import fetch_data

    database.set_db_info(user_name=user_name, user_passwd=user_passwd)
    df = fetch_data(sql, database.symbol_name, params=params)
    if strip_strings:
        df = df.map(lambda x: x.strip() if isinstance(x, str) else x)
    return df


# --------------------------------------------------------------------------
# LB903 (MariaDB)
# --------------------------------------------------------------------------
class LB903(BaseDatabase):
    """LB903 (rds-app-001, MariaDB)"""

    server_type: ClassVar[str] = "mariadb"
    server_address: ClassVar[str] = (
        "rds-app-001.cluster-ro-cjhd9sdmh8eo.ap-northeast-1.rds.amazonaws.com"
    )
    charset: ClassVar[str] = "utf8"
    username_env_key: ClassVar[str] = "LB903_USERNAME"
    password_env_key: ClassVar[str] = "LB903_PASSWORD"


class Equity(LB903):
    """LB903 > equity (指数構成・カレンダー)"""

    symbol_name: ClassVar[str] = "equity"
    db_name: ClassVar[str] = "equity"


class FactorGlb(LB903):
    """LB903 > factor_glb (オルタナティブファクター raw 値)"""

    symbol_name: ClassVar[str] = "factor_glb"
    db_name: ClassVar[str] = "factor_glb"


# --------------------------------------------------------------------------
# fs_trfac_glb (PostgreSQL)
# --------------------------------------------------------------------------
class FsTrfacGlb(BaseDatabase):
    """fs_trfac_glb (barraid / exshare)"""

    symbol_name: ClassVar[str] = "fs_trfac_glb"
    server_type: ClassVar[str] = "postgres"
    server_address: ClassVar[str] = "rds-app-002-ro.db.prod.namlab"
    db_name: ClassVar[str] = "fs_trfac_glb"
    charset: ClassVar[str] = "utf8"
    username_env_key: ClassVar[str] = "FS_TRFAC_GLB_USERNAME"
    password_env_key: ClassVar[str] = "FS_TRFAC_GLB_PASSWORD"


# --------------------------------------------------------------------------
# IRDBB (SQL Server)
# --------------------------------------------------------------------------
class IRDBB(BaseDatabase):
    """IRDBB (rds-irddb-001, SQL Server)"""

    server_type: ClassVar[str] = "sqlserver"
    server_address: ClassVar[str] = "rds-irddb-001.db.prod.namlab"
    username_env_key: ClassVar[str] = "IRDBB_USERNAME"
    password_env_key: ClassVar[str] = "IRDBB_PASSWORD"


class RiskModels(IRDBB):
    """IRDBB > RISK_MODELS (Barra GEM3)"""

    symbol_name: ClassVar[str] = "RISK_MODELS"
    db_name: ClassVar[str] = "RISK_MODELS"
    charset: ClassVar[str] = "utf8"


class Global(IRDBB):
    """IRDBB > GLOBAL (quants.FACTOR)"""

    symbol_name: ClassVar[str] = "GLOBAL"
    db_name: ClassVar[str] = "GLOBAL"
    charset: ClassVar[str] = "cp932"


# --------------------------------------------------------------------------
# その他 SQL Server
# --------------------------------------------------------------------------
class TRC(BaseDatabase):
    """TRC (RGA 指数構成・指数終値)"""

    symbol_name: ClassVar[str] = "TRC"
    server_type: ClassVar[str] = "sqlserver"
    server_address: ClassVar[str] = "172.20.172.4"
    db_name: ClassVar[str] = "TRC"
    charset: ClassVar[str] = "cp932"
    username_env_key: ClassVar[str] = "TRC_USERNAME"
    password_env_key: ClassVar[str] = "TRC_PASSWORD"


class KGX(BaseDatabase):
    """K_GX (口座保有)"""

    symbol_name: ClassVar[str] = "K_GX"
    server_type: ClassVar[str] = "sqlserver"
    server_address: ClassVar[str] = "10.49.0.1:2025"
    db_name: ClassVar[str] = "K_GX"
    charset: ClassVar[str] = "cp932"
    username_env_key: ClassVar[str] = "KGX_USERNAME"
    password_env_key: ClassVar[str] = "KGX_PASSWORD"
