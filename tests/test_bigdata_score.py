import numpy as np
import pandas as pd

from em_market_weekly.features.bigdata_score import compute_bigdata_scores


def test_composite_all_nan_row_is_nan_and_clip():
    df = pd.DataFrame(
        {
            "bid": list("abcde"),
            "rvl": [1, 2, 3, 4, np.nan],
            "TVL": [1, 2, 3, 100, np.nan],
            "NAMESG": [1, 1, 1, 1, np.nan],
        }
    )
    out = compute_bigdata_scores(df)
    assert np.isnan(out.loc[4, "culc_bigdata"])
    assert out["culc_bigdata"].abs().max() <= 3
    assert list(out.columns[:4]) == ["bid", "rvl", "TVL", "NAMESG"]


def test_partial_nan_treated_as_zero():
    df = pd.DataFrame(
        {"bid": list("abc"), "rvl": [1, 2, 3], "TVL": [np.nan] * 3, "NAMESG": [3, 2, 1]}
    )
    out = compute_bigdata_scores(df)
    expected = 0.45 * out["rvl_z"] + 0.10 * out["NAMESG_z"]
    np.testing.assert_allclose(out["composite_score"], expected)
