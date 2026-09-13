"""出力ファイルのパス規約

archive で ``/home_efs/BLF/output/...`` にハードコードされていた出力先を
``Settings`` 経由で組み立てる。各メソッドは親ディレクトリを作成してからパスを返す。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from em_market_weekly.settings import Settings

NamReturnKind = Literal["Drtn", "Srtn"]


class OutputPaths:
    """出力パスの組み立て

    Args:
        settings: アプリケーション設定。

    Examples:
        >>> paths = OutputPaths(settings)  # doctest: +SKIP
        >>> paths.score_cumulative(20260901)  # doctest: +SKIP
        PosixPath('/home_efs/BLF/output/score/cumulative/20260901.csv')
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def output_dir(self) -> Path:
        """CSV 出力のルート"""
        return self._settings.resolve(self._settings.output_dir)

    @property
    def graph_dir(self) -> Path:
        """図の出力先"""
        return self._settings.resolve(self._settings.graph_dir)

    @property
    def cache_dir(self) -> Path:
        """ローカルキャッシュのルート"""
        return self._settings.resolve(self._settings.cache_dir)

    @staticmethod
    def latest_range_file(
        directory: Path, prefix: str, from_ymd: int, to_ymd: int
    ) -> tuple[Path, int] | None:
        """``{prefix}{from_ymd}_{X}.csv`` のうち ``X <= to_ymd`` で最大のものを探す。

        増分計算の起点となる前回出力ファイルを見つけるために使う。

        Args:
            directory: 探索ディレクトリ。
            prefix: ファイル名の接頭辞 (例: ``"fret_D_"``、無ければ ``""``)。
            from_ymd: 開始日 (一致するもののみ)。
            to_ymd: 終了日の上限。

        Returns:
            ``(パス, X)``。無ければ ``None``。
        """
        if not directory.exists():
            return None
        best: tuple[Path, int] | None = None
        for p in directory.glob(f"{prefix}{from_ymd}_*.csv"):
            tail = p.stem[len(prefix) + len(str(from_ymd)) + 1 :]
            if not tail.isdigit():
                continue
            end = int(tail)
            if end <= to_ymd and (best is None or end > best[1]):
                best = (p, end)
        return best

    @staticmethod
    def _ensure(path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    # --- スコア -------------------------------------------------------------
    @property
    def score_cumulative_dir(self) -> Path:
        """銘柄×スコア累積パネルのディレクトリ"""
        d = self.output_dir / "score" / "cumulative"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def score_cumulative(self, to_ymd: int) -> Path:
        """累積パネル ``{to_ymd}.csv``"""
        return self._ensure(self.score_cumulative_dir / f"{to_ymd}.csv")

    def latest_score_cumulative(self) -> Path | None:
        """累積パネルのうち最も新しい日付のファイル。無ければ ``None``。"""
        files = [p for p in self.score_cumulative_dir.glob("*.csv") if p.stem.isdigit()]
        return max(files, key=lambda p: int(p.stem)) if files else None

    # --- ファクター ---------------------------------------------------------
    def factor_exp_common(self, from_ymd: int) -> Path:
        """共通ファクターエクスポージャ ``factor_exp_common/{from_ymd}.csv``"""
        return self._ensure(self.output_dir / "factor_exp_common" / f"{from_ymd}.csv")

    @property
    def factor_rtn_common_dir(self) -> Path:
        """共通ファクター日次リターンのディレクトリ"""
        return self.output_dir / "factor_rtn_common"

    def factor_rtn_common(self, from_ymd: int, to_ymd: int) -> Path:
        """共通ファクター日次リターン ``factor_rtn_common/fret_D_{from}_{to}.csv``"""
        return self._ensure(self.factor_rtn_common_dir / f"fret_D_{from_ymd}_{to_ymd}.csv")

    def factor_rtn_nam_dir(self, kind: NamReturnKind) -> Path:
        """NAM ファクターリターンのディレクトリ"""
        return self.output_dir / "factor_rtn_NAM" / kind

    def factor_rtn_nam(self, kind: NamReturnKind, from_ymd: int, to_ymd: int) -> Path:
        """NAM ファクターリターン ``factor_rtn_NAM/{Drtn|Srtn}/{from}_{to}.csv``"""
        return self._ensure(self.factor_rtn_nam_dir(kind) / f"{from_ymd}_{to_ymd}.csv")

    # --- スコアモニター -----------------------------------------------------
    def score_ic_dir(self, score_type: str) -> Path:
        """IC のディレクトリ"""
        return self.output_dir / "score_IC" / score_type

    def score_ic(self, score_type: str, from_ymd: int, to_ymd: int) -> Path:
        """IC ``score_IC/{score_type}/{from}_{to}.csv``"""
        return self._ensure(self.score_ic_dir(score_type) / f"{from_ymd}_{to_ymd}.csv")

    def rebalance_corr_dir(self, score_type: str) -> Path:
        """リバランス相関のディレクトリ"""
        return self.output_dir / "Rebalance_score_Corr" / score_type

    def rebalance_corr(self, score_type: str, reb_ymd: int, to_ymd: int) -> Path:
        """リバランス相関 ``Rebalance_score_Corr/{score_type}/{reb}_{to}.csv``"""
        return self._ensure(self.rebalance_corr_dir(score_type) / f"{reb_ymd}_{to_ymd}.csv")

    def active_weight_corr(self, score_type: str, from_ymd: int, to_ymd: int) -> Path:
        """アクティブウェイト相関 ``ActiveWeight_score_Corr/{score_type}/{from}_{to}.csv``"""
        return self._ensure(
            self.output_dir / "ActiveWeight_score_Corr" / score_type / f"{from_ymd}_{to_ymd}.csv"
        )

    # --- 図 ---------------------------------------------------------------
    def graph(self, name: str) -> Path:
        """図 ``{graph_dir}/{name}.png``"""
        return self._ensure(self.graph_dir / f"{name}.png")
