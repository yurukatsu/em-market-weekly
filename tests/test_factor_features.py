import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from em_market_weekly.features.factor_exposure import (
    normalize_exposures,
    weighted_category_averages,
)
from em_market_weekly.features.factor_return import daily_factor_returns
from em_market_weekly.features.nam_factor_return import (
    assign_quantiles,
    demean_by_date,
    expand_month_end_exposures,
    top_quantile_returns,
)


def test_normalize_exposures_excludes_missing_codes_and_fills_zero():
    df = pd.DataFrame(
        {"date": [1] * 3, "bid": list("abc"), "F1": [1.0, 2.0, -999.0], "F2": [3.0, np.nan, 1.0]}
    )
    out = normalize_exposures(df)
    assert out.loc["c", "F1"] == 0  # excluded then filled with 0
    assert out.loc["b", "F2"] == 0
    assert out.loc["a", "F1"] < 0 < out.loc["b", "F1"]


def test_weighted_category_averages_matches_archive_loop():
    rng = np.random.default_rng(0)
    df = pd.DataFrame(rng.normal(size=(20, 3)), columns=["A", "B", "C"])
    df["BM"] = rng.uniform(size=20)
    df["Port"] = rng.uniform(size=20)
    cats = {"X": ["A", "B"], "Y": ["C"], "Z": ["MISSING"]}
    out = weighted_category_averages(df, ["A", "B", "C"], cats)
    expected_bm_x = pd.concat([df["A"] * df["BM"], df["B"] * df["BM"]], axis=1).mean().mean()
    assert list(out["Category"]) == ["X", "Y"]
    np.testing.assert_allclose(out.loc[0, "BM Weighted Average"], expected_bm_x)
    np.testing.assert_allclose(
        out["Active Weighted Average"], out["Port Weighted Average"] - out["BM Weighted Average"]
    )


def test_daily_factor_returns_equals_sklearn_slope():
    rng = np.random.default_rng(1)
    n = 50
    exp = pd.DataFrame(
        {"bid": [f"b{i}" for i in range(n)], "F1": rng.normal(size=n), "F2": rng.normal(size=n)}
    )
    ret = pd.DataFrame({"bid": exp["bid"], "return_price_usd": rng.normal(size=n)})
    coefs = daily_factor_returns(ret, exp)
    # reproduce archive: rank -> blom -> LinearRegression per factor
    from em_market_weekly.features.transforms import blom_score

    for f in ["F1", "F2"]:
        s = blom_score(exp[f]).values.reshape(-1, 1)
        m = LinearRegression().fit(s, ret["return_price_usd"].values)
        np.testing.assert_allclose(coefs[f], m.coef_[0], rtol=1e-10)


def test_expand_and_quantiles_and_top_returns():
    me = pd.DataFrame(
        {
            "exp_date": [20260130] * 5,
            "bid": list("abcde"),
            "region": ["R1", "R1", "R1", "R2", "R2"],
            "ai": [1, 2, 3, 4, 5],
            "ai70_bd30": [5, 4, 3, 2, 1],
            "TVL": [1, 2, 3, 4, 5],
            "rvl": [1, 2, 3, 4, 5],
            "QIP": [1, 2, 3, 4, 5],
        }
    )
    exp = expand_month_end_exposures(me, [20260202, 20260203], [20260130])
    assert sorted(exp["exp_date"].unique()) == [20260202, 20260203]
    assert len(exp) == 10

    q = assign_quantiles(exp, q=5)
    assert q.loc[q["bid"] == "e", "ai_q"].iloc[0] == 5
    assert q.loc[q["bid"] == "a", "ai70_bd30_q"].iloc[0] == 5

    ret = pd.DataFrame(
        {
            "date": [20260202] * 5 + [20260203] * 5,
            "bid": list("abcde") * 2,
            "return_price_usd": [1, 2, 3, 4, 10] * 2,
        }
    )
    ret = demean_by_date(ret, "date", "return_price_usd")
    np.testing.assert_allclose(ret.groupby("date")["return_price_usd"].mean(), 0)

    top = top_quantile_returns(ret, q, date_col="date", value_col="return_price_usd", q=5)
    assert list(top.index) == [20260202, 20260203]
    assert "ai" in top.columns and "QIP" in top.columns
    np.testing.assert_allclose(top.loc[20260202, "ai"], 10 - 4)  # bid e, demeaned by mean 4
    np.testing.assert_allclose(top.loc[20260202, "ai70_bd30"], 1 - 4)  # bid a


def test_assign_quantiles_by_region():
    df = pd.DataFrame({"region": ["R1"] * 5 + ["R2"] * 5, "ai": list(range(10))})
    out = assign_quantiles(df, q=5, columns=["ai"], by_region=True)
    assert out.loc[4, "ai_q"] == 5 and out.loc[5, "ai_q"] == 1
