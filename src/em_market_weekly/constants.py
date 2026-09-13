"""プロジェクト全体で共有する定数

archive の `BLF.py` に 4 箇所重複していたファクターリストとカテゴリ辞書、
スコア種別、BigData 合成ウェイトなどをここに集約する。
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# インデックス・ベンチマーク
# --------------------------------------------------------------------------
RGA_INDEX_SYMBOL: str = "RGAEEMLN"
"""RGA ベンチマーク指数の TRC 上のシンボル"""

DEFAULT_BENCHMARK: str = "MSEM"
"""営業日カレンダーの基準にする指数コード (equity.index_global)"""

DATASTREAM_TICKERS: dict[str, str] = {"MSAC": "MSACWF$", "MSEM": "MSEMKF$"}
"""RGA 累積リターン図で比較する Datastream ティッカー"""

INDEX_LOOKBACK_DAYS: int = 400
"""指数系列の取得期間 (暦日)。末尾 ``INDEX_RETURN_WINDOW`` 営業日を含めば十分"""

INDEX_RETURN_WINDOW: int = 120
"""RGA 累積リターン図に表示する営業日数"""

# --------------------------------------------------------------------------
# スコア
# --------------------------------------------------------------------------
SCORE_TYPES: tuple[str, ...] = ("ai", "bigdata", "ai70_bd30")
"""スコアモニターで扱うスコア種別 (スコアファイルの列名)"""

SCORE_PANEL_COLUMNS: dict[str, str] = {
    "ai": "AI",
    "bigdata": "BigData",
    "ai70_bd30": "AI70_BD30",
}
"""スコア種別 → 累積パネル CSV 上の列名"""

BIGDATA_WEIGHTS: dict[str, float] = {"rvl": 0.45, "TVL": 0.45, "NAMESG": 0.10}
"""BigData 合成スコアのウェイト"""

BIGDATA_CLIP: float = 3.0
"""BigData 合成 z スコアのクリップ幅 (±)"""

NAM_FACTORS: tuple[str, ...] = ("ai", "ai70_bd30", "TVL", "rvl", "QIP")
"""NAM ファクター (Q 分位リターン計算対象)"""

NAM_PLOT_FACTORS: tuple[str, ...] = ("ai70_bd30", "ai", "TVL", "rvl")
"""NAM ファクターリターン図に描く系列 (QIP は除外)"""

TVL_FACTOR_ID: int = 400
"""factor_glb.raw_factor_area000_glb 上の TVL の factor_id"""

NAM_CALENDAR_START_YMD: int = 20250101
"""NAM ファクターリターン計算で月末を列挙する開始日"""

CALENDAR_END_YMD: int = 20301231
"""カレンダー取得の終端 (十分先の日付)"""

UNIVERSE_SCORE_COLUMNS: list[str] = [
    "sedol",
    "sedol_sub",
    "isin",
    "bid",
    "Name",
    "adjmktcap",
    "Sector",
    "Country",
    "Port",
    "BM",
    "Active",
    "AI70_BD30",
    "AI",
    "BigData",
    "Calc_BD",
    "rvl",
    "TVL",
    "NAMESG",
]
"""銘柄×スコアパネルの出力列 (順序も保持する)"""

# --------------------------------------------------------------------------
# 共通ファクター
# --------------------------------------------------------------------------
FACTOR_LIST: list[str] = [
    "BP_EST", "BP_ACT", "EP_EST", "EP_ACT", "DP_EST", "DP_ACT", "SP_EST", "SP_ACT",
    "EBITDAEV_EST", "EBITDAEV_ACT", "CFP_EST", "CFP_ACT", "OCFP", "FCFP", "RDP",
    "MARATIO", "DLT_EP3", "DLT_EP6", "TOBIN_Q", "ROE_EST", "ROE_ACT", "ROA_EST",
    "ROA_ACT", "ROIC_EST", "ROIC_ACT", "GPA_ACT", "GPA_ACT_FY", "GM_ACT", "NIS_EST",
    "NIS_ACT", "OIS_EST", "OIS_ACT", "OCFS", "PROF", "PROF_BALL_BS_FY", "LTG",
    "SALES_GRW", "OI_GRW", "EPS_GRW", "NI_GRW", "PPE_GRW", "TA_GRW", "TA_GRW_FY",
    "INVENT_GRW", "EQ_GRW", "CAPEX_GRW", "IA", "CSI", "REV1P", "REV1R", "REV3P",
    "REV3R", "MOM1", "MOM12", "MOM12_1", "AVAILM12", "MOM60", "VOLA60", "SKEW60",
    "AVAILM60", "TOVER", "ILLIQ", "DOE", "BUYBACK", "GPY", "NPY", "ACC_BS", "ACC_CF",
    "ACC_CF2", "XFIN_BS", "XFIN_CF", "XFIN_SP", "CURR", "TA_TO", "REC_TO", "INVENT_TO",
    "ACPY_TO", "CCC", "SALES_BEP", "EQR", "WK_TA", "RE_TA", "EBIT_TA", "MVE_TL",
    "SALES_TA", "SGA_TA", "RD_TA", "OCF_TA", "EQ_TL", "TDINT", "OCFTD", "PEG_EST",
    "PEG_ACT", "DSR", "GMI", "AQI", "SGI", "DEPI", "SGAI", "LEVI", "EISS", "DISS",
    "NPOP", "DLT_GPA_5Y", "DLT_ROE_5Y", "DLT_ROA_5Y", "DLT_OCFA_5Y", "DLT_GPS_5Y",
    "TD_TA", "TL_TA", "NI_TA", "PTI_TL", "INTWO", "CHIN", "NOA_FY", "NOA_GRW_FY",
    "OSCORE", "ZSCORE", "MSCORE",
]  # fmt: skip
"""GLOBAL.quants.FACTOR から取得する共通ファクター"""

FACTOR_CATEGORIES: dict[str, list[str]] = {
    "Stock Value": ["BP_EST", "BP_ACT"],
    "Flow Value": [
        "EP_EST", "EP_ACT", "DP_EST", "DP_ACT", "SP_EST", "SP_ACT", "EBITDAEV_EST",
        "EBITDAEV_ACT", "CFP_EST", "CFP_ACT", "OCFP", "FCFP", "RDP", "MARATIO",
        "DLT_EP3", "DLT_EP6", "PEG_EST", "PEG_ACT",
    ],
    "Profitability": [
        "ROE_EST", "ROE_ACT", "ROA_EST", "ROA_ACT", "ROIC_EST", "ROIC_ACT", "GPA_ACT",
        "GM_ACT", "NIS_EST", "NIS_ACT", "OIS_EST", "OIS_ACT", "OCFS", "PROF", "RE_TA",
        "EBIT_TA", "SALES_TA", "NI_TA", "PTI_TL", "CHIN", "DLT_GPA_5Y", "DLT_ROE_5Y",
        "DLT_ROA_5Y", "DLT_OCFA_5Y", "DLT_GPS_5Y",
    ],
    "Growth": [
        "LTG", "SALES_GRW", "OI_GRW", "EPS_GRW", "NI_GRW", "PPE_GRW", "TA_GRW",
        "INVENT_GRW", "EQ_GRW", "CAPEX_GRW", "IA",
    ],
    "Shareholder Return": ["CSI", "DOE", "EISS", "DISS", "NPOP"],
    "Momentum": [
        "REV1P", "REV1R", "REV3P", "REV3R", "MOM1", "MOM12", "MOM12_1", "MOM60", "TOVER",
    ],
    "Volatility": ["VOLA60", "SKEW60"],
    "Financial Quality": [
        "ACC_BS", "ACC_CF", "XFIN_BS", "XFIN_CF", "XFIN_SP", "CURR", "TA_TO", "REC_TO",
        "INVENT_TO", "ACPY_TO", "CCC", "SALES_BEP", "EQR", "MVE_TL", "EQ_TL", "TDINT",
        "OCFTD", "DSR", "GMI", "AQI", "DEPI", "SGAI", "LEVI", "TD_TA", "TL_TA",
        "OSCORE", "ZSCORE", "MSCORE",
    ],
    "Seasonality": [
        "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
    ],
}  # fmt: skip
"""共通ファクターのカテゴリ分類"""
