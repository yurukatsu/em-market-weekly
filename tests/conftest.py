"""共通フィクスチャ"""

from __future__ import annotations

from pathlib import Path

import pytest

from em_market_weekly.settings import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    """一時ディレクトリを base_dir にした設定"""
    return Settings(
        base_dir=tmp_path,
        input={
            "rga_universe": "input/universe.xlsx",
            "sedol_map": "input/sedol.xlsx",
            "region_map": "input/region.xlsx",
        },
        sftp={"score_dir": "/s", "bigdata_dir": "/b", "qip_dir": "/q"},
        accounts=[{"cd": "A", "until": 20241217}, {"cd": "B", "until": None}],
    )
