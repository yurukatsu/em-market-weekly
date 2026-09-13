"""週次の全処理 (ノートブック ``BLF_データ作成.ipynb`` 全体に相当)"""

from __future__ import annotations

from collections.abc import Sequence

from em_market_weekly.constants import SCORE_TYPES
from em_market_weekly.pipelines import (
    factor_exposure,
    factor_return,
    index_return,
    score_cumulative,
    score_monitor,
)
from em_market_weekly.pipelines.context import Context


def run(
    ctx: Context,
    from_ymd: int,
    to_ymd: int,
    inception_ymd: int,
    reb_ymd: int,
    *,
    cn: bool = True,
    q: int = 5,
    score_types: Sequence[str] = SCORE_TYPES,
) -> None:
    """A〜E と図をノートブックと同じ順序で実行する。

    Args:
        ctx: 実行コンテキスト。
        from_ymd: 週初 (強調区間の開始日)。
        to_ymd: 週末 (データ終了日)。
        inception_ymd: ファクターリターン・IC の計算開始日。
        reb_ymd: リバランス日。
        cn: NAM ファクターを地域ごとに分位化するか。
        q: 分位数。
        score_types: スコアモニターを作るスコア種別。
    """
    index_return.run(ctx, from_ymd, to_ymd)
    score_cumulative.run(ctx, to_ymd)
    factor_exposure.run(ctx, from_ymd)
    common = factor_return.run_common(ctx, inception_ymd, to_ymd)
    nam_d, nam_s = factor_return.run_nam(ctx, inception_ymd, to_ymd, cn=cn, q=q)
    factor_return.plot_all(ctx, common, nam_d, nam_s, factor_exposure.load(ctx, from_ymd), from_ymd)
    score_monitor.run(ctx, inception_ymd, to_ymd, reb_ymd, score_types, from_ymd)
