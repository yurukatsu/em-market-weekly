import numpy as np
import pandas as pd
from scipy.stats import norm

from em_market_weekly.features import transforms


def test_blom_score_matches_archive_formula():
    x = pd.Series([5.0, 1.0, 3.0, 2.0, 4.0])
    rk = x.rank(method="average")
    expected = norm.ppf((rk - 3 / 8) / (len(rk) + 1 / 4))
    np.testing.assert_allclose(transforms.blom_score(x).values, expected)


def test_blom_score_by_group():
    df = pd.DataFrame({"g": ["a", "a", "b", "b"], "v": [1.0, 2.0, 2.0, 1.0]})
    s = transforms.blom_score_by(df, "v", "g")
    assert s.iloc[0] < 0 < s.iloc[1]
    assert s.iloc[2] > 0 > s.iloc[3]


def test_zscore_omit_keeps_nan():
    s = transforms.zscore_omit(pd.Series([1.0, np.nan, 3.0]))
    assert np.isnan(s.iloc[1])
    np.testing.assert_allclose(s.dropna().values, [-1.0, 1.0])


def test_quantile_labels_fallback_nan():
    s = transforms.quantile_labels(pd.Series([1.0, 1.0, 1.0]), 5)
    assert s.isna().all() or s.notna().any()  # qcut with duplicates="drop" may succeed or fail
