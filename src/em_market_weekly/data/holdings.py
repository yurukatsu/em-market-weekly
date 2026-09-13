"""口座保有 (K_GX)"""

from __future__ import annotations

import pandas as pd

from em_market_weekly.io.database import KGX, get_data


def account_hold_daily(ymd: int, account_cd: str) -> pd.DataFrame:
    """口座の日次保有銘柄とウェイトを取得する。

    ``archive/common_function.account_hold_daily`` の移植。列名は英語化した。

    Args:
        ymd: 基準日 (``YYYYMMDD``)。
        account_cd: 口座コード。

    Returns:
        列 ``sedol`` (JP のみの口座なら ``quick``), ``name``, ``quantity``,
        ``price``, ``market_value``, ``country_code``, ``weight`` (%) を持つ DataFrame。
    """
    sql = f"""
        SELECT
            PosTDView.iss_cd AS quick, Iss.iss_name AS name, PosTDView.qty AS quantity,
            PosTDView.price AS price, PosTDView.mktval AS market_value,
            PosTDView.cntry_cd AS country_code
        FROM
            K_GX.dbo.IssInfoView Iss, K_GX.dbo.PosAssetTDView PosAsset,
            K_GX.dbo.PosTDView PosTDView
        WHERE
            PosAsset.date = PosTDView.date AND PosAsset.prt_cd = PosTDView.prt_cd
            AND PosTDView.iss_cd = Iss.iss_cd
            AND PosAsset.prt_cd = '{account_cd}' AND PosAsset.date = {ymd}
            AND PosAsset.asset_cd = 'ALL' AND PosAsset.asset_class = 1
            AND PosAsset.sec_type = 'ALL' AND PosTDView.sec_type = 'S' AND PosTDView.qty > 0
    """
    df = get_data(sql, KGX)
    df["weight"] = df["market_value"] / df["market_value"].sum() * 100
    df["quick"] = df["quick"].apply(lambda x: x.strip() if isinstance(x, str) else x)

    countries = df["country_code"].unique()
    if "JP" in countries and len(countries) > 1:
        jp_names = df.loc[df["country_code"] == "JP", "name"].tolist()
        print("JP and non-JP securities are mixed. JP names:", jp_names)

    if (df["country_code"] != "JP").any():
        df = df.rename(columns={"quick": "sedol"})
    return df
