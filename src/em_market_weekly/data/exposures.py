"""ファクターエクスポージャ (GLOBAL.quants.FACTOR / Barra GEM3 / factor_glb)"""

from __future__ import annotations

from collections.abc import Callable, Iterable

import pandas as pd

from em_market_weekly.data.calendar import business_days
from em_market_weekly.io.database import FactorGlb, Global, RiskModels, get_data


def exposure_global(ym: int, bids: Iterable[str], factors: list[str]) -> pd.DataFrame:
    """月次の共通ファクターエクスポージャ (生値) を取得する。

    ``archive/BLF.get_exp_global`` の移植。

    Args:
        ym: 年月 (``YYYYMM``)。
        bids: bid のリスト。
        factors: 取得するファクター列名。

    Returns:
        列 ``date``, ``bid`` + ``factors`` を持つ DataFrame。
    """
    quoted = "', '".join(bids)
    sql = f"""
        SELECT * FROM [GLOBAL].quants.FACTOR a
        WHERE a.[DATE] = '{ym}' AND a.BID IN ('{quoted}')
    """
    df = get_data(sql, Global)
    df = df[["DATE", "BID"] + factors]
    df.columns = ["date", "bid"] + factors
    return df


def gem3_exp_daily(from_ymd: int, to_ymd: int | None = None) -> pd.DataFrame:
    """Barra GEM3 の日次エクスポージャを取得する。

    ``archive/barra_function.gem3_exp_daily`` の移植。営業日は MSUS 基準。

    Args:
        from_ymd: 開始日 (``YYYYMMDD``)。
        to_ymd: 終了日。``None`` なら ``from_ymd`` のみ。

    Returns:
        列 ``date``, ``bid``, ``fcd``, ``exp`` を持つ DataFrame。
    """
    to_ymd = from_ymd if to_ymd is None else to_ymd
    frames = []
    for ymd in business_days("MSUS", from_ymd, to_ymd):
        sql = f"""
            SELECT DATE, BID, FCD AS fcd, EXP AS exp
            FROM GEM3_D_EXP exp
            WHERE exp.DATE = {ymd}
        """
        df = get_data(sql, RiskModels)
        df["bid"] = df["BID"].str.strip()
        frames.append(df)
    result = pd.concat(frames) if frames else pd.DataFrame(columns=["DATE", "bid", "fcd", "exp"])
    result["date"] = result["DATE"].astype("Int64")
    result["fcd"] = result["fcd"].astype("Int64")
    return result[["date", "bid", "fcd", "exp"]]


def gem3_factor_names() -> pd.DataFrame:
    """GEM3 のファクターコード → 名称 (``GEM3L_`` 接頭辞除去) を取得する。

    Returns:
        列 ``fac``, ``fcd`` を持つ DataFrame (``fcd`` 昇順)。
    """
    sql = "SELECT FAC AS fac, FCD AS fcd FROM GEM3_FAC FACTOR"
    df = get_data(sql, RiskModels).sort_values(by="fcd").reset_index(drop=True)
    df["fac"] = df["fac"].str.replace("GEM3L_", "")
    return df


def gem3_sector(ymd: int) -> pd.DataFrame:
    """Barra GEM3 の産業ファクター (fcd 200 台) から銘柄のセクター名を取得する。

    ``archive/BLF._get_sector_names`` の DB 部分。複数の産業に属する場合は
    fcd が最大のものを採用する (archive と同じ)。

    Args:
        ymd: 基準日 (``YYYYMMDD``)。

    Returns:
        列 ``bid``, ``fac`` (セクター名) を持つ DataFrame。
    """
    exp = gem3_exp_daily(ymd).query("200 < fcd < 300", engine="python")
    top = exp.loc[exp.groupby("bid")["fcd"].idxmax()]
    sector = top.set_index("bid")[["fcd"]].reset_index()
    return sector.merge(gem3_factor_names(), on="fcd", how="left")[["bid", "fac"]]


def latest_factor_glb_date(ymd: int, factor_id: int) -> int:
    """factor_glb で ``ymd`` 以前に存在する最新の effective_dateymd を返す。

    ``archive/ai_alt_score.get_latest_date_factor_glb`` の移植。

    Args:
        ymd: 基準日 (``YYYYMMDD``)。
        factor_id: ファクター ID。

    Returns:
        最新の ``effective_dateymd``。
    """
    sql = f"""
        SELECT MAX(a.effective_dateymd) AS latest_date
        FROM factor_glb.raw_factor_area000_glb AS a
        WHERE a.effective_dateymd <= {ymd} AND a.factor_id = {factor_id}
    """
    return int(get_data(sql, FactorGlb)["latest_date"].iloc[0])


def factor_glb_raw(effective_ymd: int, factor_id: int, value_name: str) -> pd.DataFrame:
    """factor_glb の raw 値を 1 日分取得する。

    Args:
        effective_ymd: ``effective_dateymd``。
        factor_id: ファクター ID。
        value_name: ``value`` 列に付ける名前 (例: ``"TVL"``)。

    Returns:
        列 ``bid``, ``value_name`` を持つ DataFrame。
    """
    sql = f"""
        SELECT bid, value AS {value_name}
        FROM factor_glb.raw_factor_area000_glb
        WHERE effective_dateymd = '{effective_ymd}' AND factor_id = {factor_id}
    """
    return get_data(sql, FactorGlb)[["bid", value_name]]


class MonthlyExposureCache:
    """同一月の ``exposure_global`` を実行中に使い回す

    ``run_common`` は営業日ごとに前月のエクスポージャを要求するが、月が同じなら
    データも同じである。要求された bid のうち未取得のものだけを問い合わせる。

    Args:
        factors: 取得するファクター列名。
        fetch: ``(ym, bids, factors) -> DataFrame`` の取得関数 (既定 ``exposure_global``)。

    Examples:
        >>> calls = []
        >>> def fake(ym, bids, factors):
        ...     calls.append(sorted(bids))
        ...     return pd.DataFrame({"date": ym, "bid": list(bids), "F1": 1.0})
        >>> cache = MonthlyExposureCache(["F1"], fetch=fake)
        >>> len(cache.get(202608, ["a", "b"])), len(cache.get(202608, ["b", "c"]))
        (2, 2)
        >>> calls
        [['a', 'b'], ['c']]
    """

    def __init__(
        self,
        factors: list[str],
        fetch: Callable[[int, Iterable[str], list[str]], pd.DataFrame] | None = None,
    ) -> None:
        self._factors = factors
        self._fetch = exposure_global if fetch is None else fetch
        self._store: dict[int, pd.DataFrame] = {}

    def get(self, ym: int, bids: Iterable[str]) -> pd.DataFrame:
        """指定月・指定 bid のエクスポージャを返す (列 ``date``, ``bid`` + factors)。

        Args:
            ym: 年月 (``YYYYMM``)。
            bids: bid のリスト。

        Returns:
            要求した bid のうちデータが存在する行。
        """
        wanted = list(dict.fromkeys(bids))
        have = self._store.get(ym)
        known = set(have["bid"]) if have is not None else set()
        missing = [b for b in wanted if b not in known]
        if missing:
            fetched = self._fetch(ym, missing, self._factors)
            have = fetched if have is None else pd.concat([have, fetched], ignore_index=True)
            self._store[ym] = have
        if have is None:
            return pd.DataFrame(columns=["date", "bid", *self._factors])
        return have[have["bid"].isin(wanted)].reset_index(drop=True)
