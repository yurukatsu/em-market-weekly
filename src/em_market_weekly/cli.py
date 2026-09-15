"""CLI エントリポイント ``em-weekly``

Examples:
    $ em-weekly weekly --from 20260826 --to 20260901 --inception 20260130 --reb 20260818
    $ em-weekly --base-dir /tmp/blf score-cumulative --to 20260901
"""

from __future__ import annotations

from pathlib import Path

import click

from em_market_weekly.constants import SCORE_TYPES
from em_market_weekly.pipelines import (
    factor_exposure,
    factor_return,
    index_return,
    score_cumulative,
    score_monitor,
    weekly,
)
from em_market_weekly.pipelines.context import Context
from em_market_weekly.settings import DEFAULT_CONFIG_PATH, DEFAULT_ENV_PATH, load_dotenv

_YMD = click.IntRange(19000101, 21001231)


@click.group()
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=DEFAULT_CONFIG_PATH,
    show_default=True,
    help="設定 YAML のパス",
)
@click.option("--base-dir", type=click.Path(path_type=Path), default=None, help="base_dir の上書き")
@click.option(
    "--output-dir", type=click.Path(path_type=Path), default=None, help="CSV 出力先の上書き"
)
@click.option(
    "--graph-dir", type=click.Path(path_type=Path), default=None, help="図の出力先の上書き"
)
@click.option(
    "--env-file",
    type=click.Path(path_type=Path),
    default=DEFAULT_ENV_PATH,
    show_default=True,
    help="認証情報を読む .env のパス (無ければ環境変数のみ)",
)
@click.option("--no-plot", is_flag=True, help="図を生成しない")
@click.option("-q", "--quiet", is_flag=True, help="進捗を表示しない")
@click.option("--recompute", is_flag=True, help="前回出力を使わず全期間を再計算する")
@click.option("--refresh-cache", is_flag=True, help="ローカルキャッシュを参照せず取り直す")
@click.pass_context
def cli(
    ctx: click.Context,
    config_path: Path,
    base_dir: Path | None,
    output_dir: Path | None,
    graph_dir: Path | None,
    env_file: Path,
    no_plot: bool,
    quiet: bool,
    recompute: bool,
    refresh_cache: bool,
) -> None:
    """新興国株式 市場レビュー用データ作成 CLI"""
    load_dotenv(env_file)
    ctx.obj = Context.from_config(
        config_path,
        base_dir=base_dir,
        output_dir=output_dir,
        graph_dir=graph_dir,
        plot=not no_plot,
        verbose=not quiet,
        recompute=recompute,
        refresh_cache=refresh_cache,
    )
    ctx.call_on_close(ctx.obj.close)


@cli.command("index-return")
@click.option("--from", "from_ymd", type=_YMD, required=True, help="強調区間の開始日 (YYYYMMDD)")
@click.option("--to", "to_ymd", type=_YMD, required=True, help="終了日 (YYYYMMDD)")
@click.pass_obj
def index_return_cmd(ctx: Context, from_ymd: int, to_ymd: int) -> None:
    """A: RGA vs MSEM / MSAC 累積リターン図"""
    index_return.run(ctx, from_ymd, to_ymd)


@cli.command("score-cumulative")
@click.option("--to", "to_ymd", type=_YMD, required=True, help="更新終了日 (YYYYMMDD)")
@click.option("--from", "from_ymd", type=_YMD, default=None, help="既存パネルが無い場合の開始日")
@click.pass_obj
def score_cumulative_cmd(ctx: Context, to_ymd: int, from_ymd: int | None) -> None:
    """B: 銘柄×スコア累積パネルの更新"""
    score_cumulative.run(ctx, to_ymd, from_ymd)


@cli.command("factor-exposure")
@click.option("--from", "from_ymd", type=_YMD, required=True, help="基準日 (YYYYMMDD)")
@click.pass_obj
def factor_exposure_cmd(ctx: Context, from_ymd: int) -> None:
    """C: 共通ファクターエクスポージャ (カテゴリ平均)"""
    factor_exposure.run(ctx, from_ymd)


@cli.group("factor-return")
def factor_return_group() -> None:
    """D: ファクターリターン"""


@factor_return_group.command("common")
@click.option("--from", "from_ymd", type=_YMD, required=True, help="開始日 (YYYYMMDD)")
@click.option("--to", "to_ymd", type=_YMD, required=True, help="終了日 (YYYYMMDD)")
@click.pass_obj
def factor_return_common_cmd(ctx: Context, from_ymd: int, to_ymd: int) -> None:
    """共通ファクターの日次リターン (回帰)"""
    factor_return.run_common(ctx, from_ymd, to_ymd)


@factor_return_group.command("nam")
@click.option("--from", "from_ymd", type=_YMD, required=True, help="開始日 (YYYYMMDD)")
@click.option("--to", "to_ymd", type=_YMD, required=True, help="終了日 (YYYYMMDD)")
@click.option("--cn/--no-cn", default=True, show_default=True, help="地域ごとに分位化する")
@click.option("--q", "q", type=int, default=5, show_default=True, help="分位数")
@click.pass_obj
def factor_return_nam_cmd(ctx: Context, from_ymd: int, to_ymd: int, cn: bool, q: int) -> None:
    """NAM ファクターの最上位分位リターン (D / S)"""
    factor_return.run_nam(ctx, from_ymd, to_ymd, cn=cn, q=q)


@factor_return_group.command("plot")
@click.option("--from", "from_ymd", type=_YMD, required=True, help="強調区間の開始日 (週初)")
@click.option("--to", "to_ymd", type=_YMD, required=True, help="終了日 (YYYYMMDD)")
@click.option(
    "--inception", "inception_ymd", type=_YMD, required=True, help="リターン CSV の開始日"
)
@click.pass_obj
def factor_return_plot_cmd(ctx: Context, from_ymd: int, to_ymd: int, inception_ymd: int) -> None:
    """保存済み CSV からファクターリターン図を再描画する"""
    common = factor_return.load_common(ctx, inception_ymd, to_ymd)
    nam_d, nam_s = factor_return.load_nam(ctx, inception_ymd, to_ymd)
    factor_return.plot_all(ctx, common, nam_d, nam_s, factor_exposure.load(ctx, from_ymd), from_ymd)


@cli.command("score-monitor")
@click.option(
    "--inception", "inception_ymd", type=_YMD, required=True, help="計算開始日 (YYYYMMDD)"
)
@click.option("--to", "to_ymd", type=_YMD, required=True, help="終了日 (YYYYMMDD)")
@click.option("--reb", "reb_ymd", type=_YMD, required=True, help="リバランス日 (YYYYMMDD)")
@click.option("--from", "from_ymd", type=_YMD, default=None, help="図の強調区間の開始日 (週初)")
@click.option(
    "--score-type",
    type=click.Choice([*SCORE_TYPES, "all"]),
    default="all",
    show_default=True,
)
@click.pass_obj
def score_monitor_cmd(
    ctx: Context,
    inception_ymd: int,
    to_ymd: int,
    reb_ymd: int,
    from_ymd: int | None,
    score_type: str,
) -> None:
    """E: スコアモニター (IC / リバランス相関 / アクティブウェイト相関)"""
    types = SCORE_TYPES if score_type == "all" else (score_type,)
    score_monitor.run(ctx, inception_ymd, to_ymd, reb_ymd, types, from_ymd)


@cli.command("weekly")
@click.option("--from", "from_ymd", type=_YMD, required=True, help="週初 (YYYYMMDD)")
@click.option("--to", "to_ymd", type=_YMD, required=True, help="週末 (YYYYMMDD)")
@click.option(
    "--inception", "inception_ymd", type=_YMD, required=True, help="計算開始日 (YYYYMMDD)"
)
@click.option("--reb", "reb_ymd", type=_YMD, required=True, help="リバランス日 (YYYYMMDD)")
@click.option(
    "--cn/--no-cn", default=True, show_default=True, help="NAM ファクターを地域ごとに分位化する"
)
@click.option("--q", "q", type=int, default=5, show_default=True, help="分位数")
@click.pass_obj
def weekly_cmd(
    ctx: Context, from_ymd: int, to_ymd: int, inception_ymd: int, reb_ymd: int, cn: bool, q: int
) -> None:
    """A〜E と図を全て実行する (ノートブック全体に相当)"""
    weekly.run(ctx, from_ymd, to_ymd, inception_ymd, reb_ymd, cn=cn, q=q)


if __name__ == "__main__":
    cli()
