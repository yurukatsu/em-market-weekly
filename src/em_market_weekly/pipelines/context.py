"""パイプライン実行時のコンテキスト (設定・出力パス・キャッシュ・外部クライアント)"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from matplotlib.figure import Figure

from em_market_weekly.data.scores import ScoreStore
from em_market_weekly.io.cache import FileCache
from em_market_weekly.io.datastream import DatastreamClient
from em_market_weekly.io.paths import OutputPaths
from em_market_weekly.io.sftp import ItaapClient
from em_market_weekly.settings import Settings


@dataclass
class Context:
    """パイプラインが共有する実行環境

    Attributes:
        settings: アプリケーション設定。
        plot: ``True`` なら図を生成・保存する。
        verbose: ``True`` なら進捗を表示する。
        recompute: ``True`` なら前回出力を使わず全期間を再計算する。
        refresh_cache: ``True`` ならローカルキャッシュを参照せず取り直す (保存はする)。

    Examples:
        >>> ctx = Context.from_config("config/settings.yaml")  # doctest: +SKIP
        >>> ctx.paths.score_cumulative(20260901)  # doctest: +SKIP
    """

    settings: Settings
    plot: bool = True
    verbose: bool = True
    recompute: bool = False
    refresh_cache: bool = False
    _scores: ScoreStore | None = field(default=None, init=False, repr=False)
    _datastream: DatastreamClient | None = field(default=None, init=False, repr=False)
    _cache: FileCache | None = field(default=None, init=False, repr=False)

    @classmethod
    def from_config(
        cls,
        config_path: Path | str,
        *,
        base_dir: Path | str | None = None,
        output_dir: Path | str | None = None,
        graph_dir: Path | str | None = None,
        plot: bool = True,
        verbose: bool = True,
        recompute: bool = False,
        refresh_cache: bool = False,
    ) -> Context:
        """YAML と上書き値からコンテキストを作る。

        Args:
            config_path: 設定 YAML のパス。
            base_dir: ``base_dir`` の上書き。
            output_dir: ``output_dir`` の上書き。
            graph_dir: ``graph_dir`` の上書き。
            plot: 図を生成するか。
            verbose: 進捗を表示するか。
            recompute: 全期間を再計算するか。
            refresh_cache: キャッシュを取り直すか。

        Returns:
            コンテキスト。
        """
        settings = Settings.load(
            config_path,
            overrides={"base_dir": base_dir, "output_dir": output_dir, "graph_dir": graph_dir},
        )
        return cls(
            settings=settings,
            plot=plot,
            verbose=verbose,
            recompute=recompute,
            refresh_cache=refresh_cache,
        )

    @property
    def paths(self) -> OutputPaths:
        """出力パス"""
        return OutputPaths(self.settings)

    @property
    def cache(self) -> FileCache:
        """ローカルファイルキャッシュ"""
        if self._cache is None:
            self._cache = FileCache(
                self.paths.cache_dir,
                revision_window_days=self.settings.revision_window_days,
                refresh=self.refresh_cache,
            )
        return self._cache

    @property
    def scores(self) -> ScoreStore:
        """スコアファイルストア (キャッシュ優先、SFTP は必要時のみ接続)"""
        if self._scores is None:
            self._scores = ScoreStore(self.settings, self.cache, ItaapClient.from_env)
        return self._scores

    @property
    def datastream(self) -> DatastreamClient:
        """Datastream クライアント (初回アクセス時に環境変数から生成)"""
        if self._datastream is None:
            self._datastream = DatastreamClient.from_env()
        return self._datastream

    def log(self, message: str) -> None:
        """``verbose`` のときだけメッセージを表示する。"""
        if self.verbose:
            print(message)

    def save_figure(self, fig: Figure, name: str) -> Path | None:
        """``plot`` が有効なら図を保存して閉じる。

        Args:
            fig: 保存する Figure。
            name: ファイル名 (拡張子なし)。

        Returns:
            保存先。``plot`` が無効なら ``None``。
        """
        import matplotlib.pyplot as plt

        path = None
        if self.plot:
            path = self.paths.graph(name)
            fig.savefig(path)
            self.log(f"Save to {path}")
        plt.close(fig)
        return path

    def close(self) -> None:
        """外部接続を閉じる。"""
        if self._scores is not None:
            self._scores.close()
            self._scores = None
