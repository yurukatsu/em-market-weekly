from pathlib import Path

import pytest

from em_market_weekly.io.paths import OutputPaths
from em_market_weekly.settings import Settings


def test_account_cd_by_date(settings: Settings):
    assert settings.account_cd(20241217) == "A"
    assert settings.account_cd(20241218) == "B"


def test_resolve_relative_and_absolute(settings: Settings, tmp_path: Path):
    assert settings.resolve("x/y.csv") == tmp_path / "x" / "y.csv"
    assert settings.resolve("/abs/y.csv") == Path("/abs/y.csv")


def test_load_with_overrides(tmp_path: Path):
    cfg = tmp_path / "s.yaml"
    cfg.write_text(
        "base_dir: /base\n"
        "input: {rga_universe: a.xlsx, sedol_map: b.xlsx, region_map: c.xlsx}\n"
        "sftp: {score_dir: /s, bigdata_dir: /b, qip_dir: /q}\n",
        encoding="utf-8",
    )
    s = Settings.load(cfg, overrides={"base_dir": "/other", "output_dir": None})
    assert s.base_dir == Path("/other")
    assert s.output_dir == Path("output")


def test_output_paths_create_dirs_and_latest(settings: Settings, tmp_path: Path):
    paths = OutputPaths(settings)
    assert paths.latest_score_cumulative() is None
    p1 = paths.score_cumulative(20260101)
    p1.write_text("x")
    p2 = paths.score_cumulative(20260201)
    p2.write_text("x")
    assert paths.latest_score_cumulative() == p2
    assert paths.factor_rtn_nam("Drtn", 1, 2).parent.is_dir()
    assert paths.graph("g") == tmp_path / "latest_graph" / "g.png"


def test_account_cd_no_match():
    s = Settings(
        base_dir="/b",
        input={"rga_universe": "a", "sedol_map": "b", "region_map": "c"},
        sftp={"score_dir": "/s", "bigdata_dir": "/b", "qip_dir": "/q"},
        accounts=[{"cd": "A", "until": 20200101}],
    )
    with pytest.raises(ValueError):
        s.account_cd(20260101)
