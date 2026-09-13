"""A: RGA vs MSEM / MSAC 累積リターン図"""

from __future__ import annotations

from pathlib import Path

from em_market_weekly.constants import DATASTREAM_TICKERS, INDEX_LOOKBACK_DAYS, INDEX_RETURN_WINDOW
from em_market_weekly.data.rga_index import rga_index_close
from em_market_weekly.dates import shift_days
from em_market_weekly.features.index_return import cumulative_return_difference, tail_cumulative
from em_market_weekly.pipelines.context import Context
from em_market_weekly.plots.index_return import plot_index_return


def run(ctx: Context, from_ymd: int, to_ymd: int) -> Path | None:
    """RGA / MSEM / MSAC の直近 120 営業日の累積リターン図を作成する。

    ノートブック内 ``RGA_Rtn_graph(from_ymd, to_ymd)`` の置き換え。
    取得期間は末尾 120 営業日を含む ``INDEX_LOOKBACK_DAYS`` 暦日に限定する。

    Args:
        ctx: 実行コンテキスト。
        from_ymd: 強調区間 (黄色背景) の開始日。
        to_ymd: 取得終了日。

    Returns:
        保存した図のパス (``ctx.plot`` が無効なら ``None``)。
    """
    start = shift_days(to_ymd, -INDEX_LOOKBACK_DAYS)
    rga = rga_index_close(to_ymd, start)
    msac = ctx.datastream.price_series(DATASTREAM_TICKERS["MSAC"], start, to_ymd)
    msem = ctx.datastream.price_series(DATASTREAM_TICKERS["MSEM"], start, to_ymd)

    rga_t = tail_cumulative(rga, "Close", INDEX_RETURN_WINDOW)
    msem_t = tail_cumulative(msem, "Price", INDEX_RETURN_WINDOW)
    msac_t = tail_cumulative(msac, "Price", INDEX_RETURN_WINDOW)
    diff = cumulative_return_difference(rga_t, msem_t)

    fig = plot_index_return(rga_t, msem_t, msac_t, diff, from_ymd, to_ymd)
    return ctx.save_figure(fig, "RGA_rtn")
