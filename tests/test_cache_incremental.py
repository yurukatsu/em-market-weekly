from pathlib import Path

import pandas as pd
import pytest

from em_market_weekly.data.exposures import MonthlyExposureCache
from em_market_weekly.data.scores import ScoreStore
from em_market_weekly.io.cache import FileCache
from em_market_weekly.io.paths import OutputPaths
from em_market_weekly.pipelines.incremental import (
    load_kept_rows,
    make_plan,
    merge_rows,
    to_ymd_series,
)
from em_market_weekly.settings import Settings


# ----------------------------------------------------------------------
# FileCache
# ----------------------------------------------------------------------
def test_file_cache_only_trusts_final_dates(tmp_path: Path):
    cache = FileCache(tmp_path, revision_window_days=10, today=20260914)
    df = pd.DataFrame({"a": [1]})
    cache.put("k", 20260901, df)  # final -> stored
    cache.put("k", 20260910, df)  # within window -> not stored
    assert cache.get("k", 20260901) is not None
    assert cache.get("k", 20260910) is None
    assert not (tmp_path / "k" / "20260910.pkl").exists()


def test_file_cache_missing_marker_and_refresh(tmp_path: Path):
    cache = FileCache(tmp_path, revision_window_days=10, today=20260914)
    cache.mark_missing("k", 20260830)
    assert cache.is_missing("k", 20260830)
    cache.put("k", 20260830, pd.DataFrame({"a": [1]}))
    assert not cache.is_missing("k", 20260830)

    refresh = FileCache(tmp_path, revision_window_days=10, today=20260914, refresh=True)
    assert refresh.get("k", 20260830) is None
    assert not refresh.is_missing("k", 20260830)


# ----------------------------------------------------------------------
# ScoreStore (SFTP を使わずにキャッシュだけで動く)
# ----------------------------------------------------------------------
class _FakeClient:
    def __init__(self, files: dict[str, pd.DataFrame]):
        self.files = files
        self.reads: list[str] = []
        self.closed = False

    def read_csv(self, path: str) -> pd.DataFrame:
        self.reads.append(path)
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    def read_dat(self, path: str) -> pd.DataFrame:
        return self.read_csv(path)

    def close(self) -> None:
        self.closed = True


def _store(settings: Settings, tmp_path: Path, client: _FakeClient, today=20260914) -> ScoreStore:
    cache = FileCache(tmp_path / "cache", revision_window_days=10, today=today)
    return ScoreStore(settings, cache, lambda: client)


def test_score_store_walks_back_and_caches(settings: Settings, tmp_path: Path):
    score = pd.DataFrame({"bid": ["a"], "ai": [1.0], "bigdata": [2.0], "ai70_bd30": [3.0]})
    client = _FakeClient({"/s/20260828.csv": score})
    store = _store(settings, tmp_path, client)

    df, found = store.ai_score_daily(20260830)
    assert found == 20260828 and len(client.reads) == 3

    # 2 回目はキャッシュだけで解決する (missing マーカー + 実体)
    client2 = _FakeClient({})
    store2 = _store(settings, tmp_path, client2)
    df2, found2 = store2.ai_score_daily(20260830)
    assert found2 == 20260828 and client2.reads == []
    pd.testing.assert_frame_equal(df, df2)
    assert store2._client is None  # SFTP 接続は開かれていない


def test_score_store_recent_dates_bypass_cache(settings: Settings, tmp_path: Path):
    score = pd.DataFrame({"bid": ["a"], "ai": [1.0], "bigdata": [2.0], "ai70_bd30": [3.0]})
    client = _FakeClient({"/s/20260912.csv": score})
    store = _store(settings, tmp_path, client)
    store.ai_score_daily(20260912)
    store.ai_score_daily(20260912)
    assert len(client.reads) == 2  # ウィンドウ内なので毎回取り直す


def test_bigdata_fallback_and_columns(settings: Settings, tmp_path: Path):
    bd = pd.DataFrame({"bid": ["a"], "tvl": [1.0], "rvl": [2.0], "nam": [3.0], "x": [0]})
    client = _FakeClient({"/b/20260201.csv": bd})
    store = _store(settings, tmp_path, client)
    with pytest.raises(FileNotFoundError):
        store.bigdata_daily(20260301, max_lookback=2)
    df, found = store.bigdata_daily(20260301, max_lookback=2, fallback_ymd=20260201)
    assert found == 20260201 and list(df.columns) == ["bid", "TVL", "rvl", "NAMESG"]


def test_qip_monthly_header_and_numeric(settings: Settings, tmp_path: Path):
    raw = pd.DataFrame(
        [["bid", "invention_count_12m", "tassets", "sales"], ["a", "10", "100", "x"]]
    )
    client = _FakeClient({"/q/202607.dat": raw})
    store = _store(settings, tmp_path, client)
    df = store.qip_monthly(202607)
    assert df.loc[0, "invention_count_12m"] == 10 and pd.isna(df.loc[0, "sales"])
    # 確定済み月なのでキャッシュされ、2 回目は読まない
    store.qip_monthly(202607)
    assert len(client.reads) == 1


# ----------------------------------------------------------------------
# MonthlyExposureCache
# ----------------------------------------------------------------------
def test_monthly_exposure_cache_fetches_only_missing():
    calls = []

    def fake(ym, bids, factors):
        calls.append((ym, sorted(bids)))
        return pd.DataFrame({"date": ym, "bid": list(bids), "F1": 1.0})

    cache = MonthlyExposureCache(["F1"], fetch=fake)
    assert len(cache.get(202608, ["a", "b"])) == 2
    assert len(cache.get(202608, ["b", "c"])) == 2
    assert len(cache.get(202607, ["a"])) == 1
    assert calls == [(202608, ["a", "b"]), (202608, ["c"]), (202607, ["a"])]


# ----------------------------------------------------------------------
# incremental
# ----------------------------------------------------------------------
DAYS = [20260825, 20260826, 20260827, 20260828, 20260831, 20260901]


def test_make_plan_variants():
    p = make_plan(DAYS, 20260828, 20260901, 3)
    assert p.cutoff == 20260828 and p.compute_days == [20260831, 20260901]
    p = make_plan(DAYS, 20260901, 20260901, 3)
    assert p.cutoff == 20260829 and p.compute_days == [20260831, 20260901]
    p = make_plan(DAYS, 20260901, 20260901, 3, recompute=True)
    assert p.full and p.compute_days == DAYS
    p = make_plan(DAYS, 20260801, 20260901, 3)
    assert p.cutoff == 20260801 and p.compute_days == DAYS


def test_load_kept_rows_and_merge(tmp_path: Path):
    csv = tmp_path / "x.csv"
    pd.DataFrame({"date": ["2026-08-27", "2026-08-28", "2026-08-31"], "c": [1.0, 2.0, 3.0]}).to_csv(
        csv, index=False
    )
    plan = make_plan(DAYS, 20260831, 20260901, 3)  # cutoff = 20260829
    kept = load_kept_rows(csv, "date", plan)
    assert kept["date"].tolist() == ["2026-08-27", "2026-08-28"]
    new = pd.DataFrame(
        {"date": ["2026-08-28", "2026-08-31", "2026-09-01"], "c": [20.0, 30.0, 40.0]}
    )
    merged = merge_rows(kept, new, "date")
    assert merged["c"].tolist() == [1.0, 20.0, 30.0, 40.0]
    assert load_kept_rows(csv, "date", make_plan(DAYS, None, 20260901, 3)) is None


def test_to_ymd_series_dates():
    import datetime

    s = pd.Series([datetime.date(2026, 9, 1)])
    assert to_ymd_series(s).tolist() == [20260901]


def test_latest_range_file(settings: Settings):
    paths = OutputPaths(settings)
    d = paths.factor_rtn_common_dir
    assert paths.latest_range_file(d, "fret_D_", 20260130, 20260901) is None
    for end in (20260814, 20260821, 20260828, 20260904):
        paths.factor_rtn_common(20260130, end).write_text("x")
    paths.factor_rtn_common(20260201, 20260828).write_text("x")
    found = paths.latest_range_file(d, "fret_D_", 20260130, 20260901)
    assert found is not None and found[1] == 20260828
    assert paths.latest_range_file(paths.factor_rtn_nam_dir("Drtn"), "", 20260130, 20260901) is None
