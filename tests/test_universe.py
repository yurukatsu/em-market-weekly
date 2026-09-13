import numpy as np
import pandas as pd

from em_market_weekly.constants import UNIVERSE_SCORE_COLUMNS
from em_market_weekly.features import universe as U


def _universe():
    return pd.DataFrame(
        {
            "English Name": ["Alpha", "Beta", "Gamma"],
            "isin": ["I1", "I2", "I3"],
            "sedol": ["S1", "S2", "S3"],
            "region": ["CN", "IN", "BR"],
            "Exchange": ["X", "X", "X"],
        }
    )


def _sedol_map():
    return pd.DataFrame({"from_sedol": ["H2"], "to_sedol": ["S2"]})


def test_full_link_pipeline():
    uni = U.prepare_universe(_universe(), _sedol_map().set_index("to_sedol")["from_sedol"])
    assert uni.loc[1, "sedol_chg"] == "H2"

    rga = pd.DataFrame(
        {
            "sedol": ["S1", "H2", "S9"],
            "bid": ["B1", "B2", "B9"],
            "adjmktcap": [10, 20, 30],
            "weight": [1.0, 2.0, 3.0],
        }
    )
    df = U.link_rga_universe(uni, rga)
    # H2 matched via sedol_chg -> Beta gets bid/weight; S9 appended as new row
    beta = df[df["English Name"] == "Beta"].iloc[0]
    assert beta["bid"] == "B2" and beta["weight"] == 2.0
    assert "S9" in df["sedol"].values

    holdings = pd.DataFrame(
        {
            "sedol": ["H2", "S3", "S7"],
            "name": ["Beta-h", "Gamma-h", "Extra"],
            "weight": [5.0, 6.0, 7.0],
            "country_code": ["IN", "BR", "US"],
        }
    )
    df = U.link_positions(df, holdings)
    assert {"Name", "Country", "weight_RGA", "weight_BLF", "sedol", "sedol_sub"} <= set(df.columns)
    extra = df[df["Name"] == "Extra"].iloc[0]
    assert extra["Country"] == "US" and extra["weight_BLF"] == 7.0

    df = U.add_active_weight(df)
    alpha = df[df["Name"] == "Alpha"].iloc[0]
    assert alpha["weight_ACT"] == -1.0

    score = pd.DataFrame(
        {"sedol": ["S1", "H2"], "ai70_bd30": [0.1, 0.2], "ai": [1.0, 2.0], "bigdata": [3.0, 4.0]}
    )
    df = U.link_ai_score(df, score)
    assert df[df["Name"] == "Alpha"].iloc[0]["ai"] == 1.0
    beta = df[df["Name"] == "Beta"].iloc[0]
    assert beta["ai"] == 2.0  # via sedol_sub (H2)

    code_map = pd.DataFrame({"bid": ["B3"], "sedol": ["S3"]})
    df = U.attach_bid(df, code_map)
    assert df[df["Name"] == "Gamma"].iloc[0]["bid"] == "B3"
    assert df[df["Name"] == "Alpha"].iloc[0]["bid"] == "B1"

    df = U.attach_sector(df, pd.DataFrame({"bid": ["B1"], "fac": ["Energy"]}))
    bigdata = pd.DataFrame(
        {"bid": ["B1"], "rvl_z": [0.5], "TVL_z": [0.6], "NAMESG_z": [0.7], "culc_bigdata": [0.8]}
    )
    df = U.attach_bigdata(df, bigdata)
    out = U.finalize_columns(df)
    assert list(out.columns) == UNIVERSE_SCORE_COLUMNS
    alpha = out[out["Name"] == "Alpha"].iloc[0]
    assert alpha["Sector"] == "Energy" and alpha["Calc_BD"] == 0.8 and alpha["BM"] == 1.0
    assert np.isnan(out[out["Name"] == "Gamma"].iloc[0]["Calc_BD"])
