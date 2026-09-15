# BLF_データ作成.ipynb リファクタリング計画

作成日: 2026-09-14

## 1. 現状分析

### 1.1 ノートブックがやっていること

`archive/BLF_データ作成.ipynb` は `archive/BLF.py` の関数を順番に呼ぶ薄いドライバである。
入力パラメータは 4 つ（`from_ymd`, `to_ymd`, `inception_ymd`, `reb_ymd`）。処理は 5 ブロックに分かれる。

| # | ブロック | 呼び出し | 入力 | 出力 |
|---|---|---|---|---|
| A | RGA vs MSEM/MSAC 累積リターン | `RGA_Rtn_graph` (nb 内定義) | TRC DB, Datastream | `latest_graph/RGA_rtn.png` |
| B | 銘柄×スコアの累積パネル更新 | `update_score_cumlative` | TRC, K_GX, fs_trfac_glb, RISK_MODELS, barra, SFTP(score/bigdata), xlsx×2 | `output/score/cumulative/{to}.csv` |
| C | ファクターエクスポージャ | `port_fct_exp` | B の 1 日分 + GLOBAL DB | `output/factor_exp_common/{from}.csv` |
| D | ファクターリターン | `fret_em_daily` / `fret_nam_daily` | SFTP score, GLOBAL, fs_trfac_glb, RISK_MODELS, factor_glb, SFTP(qip .dat), TRC | `factor_rtn_common/…csv`, `factor_rtn_NAM/{Drtn,Srtn}/…csv` |
| E | スコアモニター (×3 score_type) | `score_IC_Reb`, `ActiveWeight_score_Corr` | SFTP score, fs_trfac_glb, equity, B の出力 | `score_IC/…`, `Rebalance_score_Corr/…`, `ActiveWeight_score_Corr/…` |
| 図 | プロット | `plot_factor_exp`, `plot_Common_factor_Drtn`, `plot_NAM_factor_Drtn`, `plot_NAM_factor_Srtn`, `plot_Score_monitor` | C/D/E の CSV | `latest_graph/*.png` |

依存関係: A は独立。B → C、B → E(ActiveWeight)。D は独立。図は各 CSV に依存。

### 1.2 外部依存の棚卸し

**データベース（pylabcore 経由）** — `sql_connect_new.py` に既にあるもの: `equity`, `fs_trfac_glb`, `RISK_MODELS`。
追加が必要なもの:

| symbol | server_type | server_address | charset | 用途 |
|---|---|---|---|---|
| `TRC` | sqlserver | 172.20.172.4 | cp932 | RGA 構成銘柄・指数終値 |
| `GLOBAL` | sqlserver | rds-irddb-001.db.prod.namlab | cp932 | `quants.FACTOR` エクスポージャ |
| `K_GX` | sqlserver | 10.49.0.1:2025 | cp932 | 口座保有 (`account_hold_daily`) |
| `factor_glb` | mariadb | rds-app-001.cluster-ro-… | utf8 | TVL raw factor |

**SFTP (itaap, paramiko)** — `common_function.itaap_read_file`。認証情報がハードコードされている。
- `/abe/blf/score/daily/{ymd}.csv` (AI / bigdata / ai70_bd30 スコア)
- `/abe/blf/score/daily/bigdata/{ymd}.csv` (tvl / rvl / nam)
- `/k-manabe/share/qip/current/rga/{ym}.dat` (QIP)

**LSEG Datastream (DatastreamPy)** — 認証情報がハードコード。`MSACWF$`, `MSEMKF$`。

**ローカルファイル (`/home_efs/BLF/...`)**
- 入力: `input/RGA_universe/emDynExTWholdListJun2026.xlsx`, `input/sedol対応表/BLF_sedol変換表_202501.xlsx`, `input/region_map.xlsx`
- 出力: `output/**/*.csv`, `latest_graph/*.png`

**archive に無いモジュール（要確認）**
- `barra_function.gem3_exp_daily(dateymd)` — セクター付与に使用
- `ai_alt_score.get_latest_date_factor_glb(ymd, factor_id)`, `ai_alt_score.get_pym(ym, n)`, `ai_alt_score.calc_blom_score(series, alpha)` — `fret_nam_daily` で使用

### 1.3 既存コードの問題点（リファクタリングで解消するもの）

1. **重複コード**: `factor_list` / `factor_categories` が 4 箇所、bigdata z-score 計算が 2 箇所、Blom 順位正規化が 2 箇所、「日付を遡ってファイルを探す」ループが 5 箇所、「累積和＋from_ymd 以降を強調する折れ線」プロットが 3 箇所。
2. **I/O と計算の密結合**: ほぼ全関数が DB 取得・計算・CSV 保存・`plt.show()` を一つの関数でやっている。テスト不能。
3. **パスの不整合**: `update_score_cumlative` は `os.getcwd()/output/score/cumulative` を読むが、`ActiveWeight_score_Corr` は `/home_efs/BLF/output/score/cumulative` を読む。
4. **認証情報のハードコード**: Datastream, SFTP, DB。
5. **潜在バグ**: `_get_past_bigdata_factors` は `str` に `.strftime` を呼んでおり実行時エラーになる（ノートブックからは未使用の `RGA_universe_score_1Mdif` 経由のみ）。
6. **マジックナンバー**: 口座コード切替日 `20241217`、bigdata 最古日 `20260201`、120 営業日、`0.45/0.45/0.10` の合成ウェイト、など。
7. **型注釈・docstring なし**。

## 2. 設計方針

- **レイヤ分離**: `io`（接続）→ `data`（取得、DataFrame を返す）→ `features`（純粋計算、I/O なし）→ `pipelines`（取得→計算→保存の手順）→ `cli`。`plots` は `features` の出力 DataFrame を受け取り図を返す。
- **計算ロジックは archive と同一結果を保つ**。ロジックの改善（例: 回帰の高速化）は本リファクタでは行わない。同一日付で archive と新実装の CSV を突き合わせて検証する。
- **パス・認証情報は設定に外出し**: YAML（パス、口座コード等）と環境変数（認証情報）。`pydantic` v2 は会社環境で使用可なので `BaseSettings` 相当を自前実装するか `pydantic` のモデル + `PyYAML` で読む。
- **自宅環境でも import・テストが通る**: `pylabcore`, `DatastreamPy`, `paramiko` は関数内で遅延 import。`features` は DataFrame 入力のみなので自宅で単体テスト可能。
- **プロットは保存のみ**: `plt.show()` は CLI では呼ばない。図の生成関数は `Figure` を返し、保存は pipeline が行う。
- **ノートブック互換の API も残す**: `pipelines` の関数を notebook から直接呼べるようにする（CLI は薄いラッパ）。

## 3. フォルダ構造案

```
em-market-weekly/
├── pyproject.toml
├── CLAUDE.md
├── README.md
├── config/
│   ├── settings.yaml             # 会社環境用（git 管理: パスのみ、秘密情報なし）
│   └── settings.example.yaml     # 雛形
├── docs/
│   └── refactoring_plan.md       # 本書
├── archive/                      # 参照用。移植完了・検証後に削除
├── src/em_market_weekly/
│   ├── __init__.py
│   ├── cli.py                    # click グループ `em-weekly`
│   ├── settings.py               # YAML + 環境変数 → Settings (paths, account codes, credentials)
│   ├── constants.py              # FACTOR_LIST, FACTOR_CATEGORIES, SCORE_TYPES, BIGDATA_WEIGHTS など
│   ├── dates.py                  # 日付ヘルパー (純粋関数): previous_month, nearest_on_or_before, month_ends
│   │
│   ├── io/                       # 外部システムへの接続。DataFrame は返さないか、生データのみ返す
│   │   ├── __init__.py
│   │   ├── database.py           # sql_connect_new.py を移植 + TRC / Global / KGX / FactorGlb を追加
│   │   ├── sftp.py               # ItaapClient: read_csv / read_dat / read_latest_on_or_before(path_fn, ymd)
│   │   ├── datastream.py         # DatastreamClient: get_price_index(ticker, start, end)
│   │   └── paths.py              # Settings から入出力パスを組み立てる (OutputPaths)
│   │
│   ├── data/                     # SQL / ファイル → 整形済み DataFrame。計算は含めない
│   │   ├── __init__.py
│   │   ├── calendar.py           # bm_calendar, business_days (equity DB)
│   │   ├── rga_index.py          # rga_bm_weight, rga_calendar, rga_index_close
│   │   ├── holdings.py           # account_hold_daily (K_GX)
│   │   ├── security_master.py    # code_change (barraid), bid_to_namid
│   │   ├── returns.py            # ret_usd_daily, ret_global_daily, sret_global_daily
│   │   ├── exposures.py          # exposure_global (GLOBAL.quants.FACTOR), gem3_sector, tvl_raw (factor_glb)
│   │   ├── scores.py             # ai_score_daily, bigdata_daily, qip_monthly  (SFTP 経由、日付フォールバック込み)
│   │   └── universe_files.py     # RGA ユニバース xlsx, sedol 変換表, region_map
│   │
│   ├── features/                 # 純粋計算。DataFrame in → DataFrame out。I/O 禁止
│   │   ├── __init__.py
│   │   ├── transforms.py         # blom_rank_normalize, zscore_clip, quantile_rank, category_mean
│   │   ├── bigdata_score.py      # composite bigdata score (0.45/0.45/0.10 → zscore → clip ±3)
│   │   ├── universe.py           # build_universe_score: link_rga, link_positions, active_weight, link_ai_score, link_sector
│   │   ├── factor_exposure.py    # category-weighted averages (BM / Port / Active)
│   │   ├── factor_return.py      # cross-sectional regression → daily common-factor return
│   │   ├── nam_factor_return.py  # Q-quantile portfolio return (D / S) for NAM factors
│   │   ├── score_monitor.py      # ic_by_date, rebalance_corr, active_weight_corr
│   │   └── index_return.py       # cumulative return & RGA−MSEM difference
│   │
│   ├── plots/                    # DataFrame → matplotlib Figure。保存は呼び出し側
│   │   ├── __init__.py
│   │   ├── style.py              # 色定義、from_ymd 以降ハイライトの共通ヘルパ
│   │   ├── index_return.py       # RGA_Rtn_graph 相当
│   │   ├── factor_exposure.py    # plot_factor_exp 相当
│   │   ├── cumulative_lines.py   # Common / NAM Drtn / NAM Srtn の共通実装 (3 関数 → 1 関数 + 引数)
│   │   └── score_monitor.py      # plot_Score_monitor 相当
│   │
│   └── pipelines/                # data → features → 保存 → plots。CLI とノートブックの両方から呼ぶ
│       ├── __init__.py
│       ├── context.py            # Context: settings / paths / SFTP / Datastream クライアント
│       ├── index_return.py       # A
│       ├── score_cumulative.py   # B
│       ├── factor_exposure.py    # C
│       ├── factor_return.py      # D (common / nam)
│       ├── score_monitor.py      # E
│       └── weekly.py             # A〜E + 図をまとめて実行
│
└── tests/
    ├── conftest.py               # 小さな DataFrame フィクスチャ
    ├── test_transforms.py
    ├── test_bigdata_score.py
    ├── test_universe.py
    ├── test_factor_return.py
    ├── test_score_monitor.py
    └── test_calendar.py
```

### 3.1 archive 関数 → 新モジュール対応表

| archive | 新配置 | 備考 |
|---|---|---|
| nb `RGA_Rtn_graph` | `data/rga_index.rga_index_close`, `io/datastream`, `features/index_return`, `plots/index_return`, `pipelines/index_return` | 取得・計算・描画を分離 |
| `RGA_BM_weight` | `data/rga_index.rga_bm_weight` | sedol 変換表の適用は `data/universe_files` から受け取る |
| `_create_calendar` | `data/rga_index.rga_calendar` + `calendar.nearest_date_on_or_before` | |
| `_get_basic_data` | `data/universe_files`, `data/holdings`, `data/scores.ai_score_daily` | 口座コード切替を `settings` に |
| `_link_*`, `_calculate_active_weight`, `_get_sector_names`, `_rename_columns` | `features/universe` | `_get_sector_names` の DB 部分は `data/exposures.gem3_sector` へ |
| `_get_bigdata_factors` | `data/scores.bigdata_daily` | フォールバック探索は `io/sftp.read_latest_on_or_before` に集約 |
| `_calculate_bigdata_scores`, `_calculate_composite_score` | `features/bigdata_score` | past 版と統合 |
| `RGA_universe_score` | `features/universe.build_universe_score` + `pipelines/score_cumulative.universe_score_for_date` | |
| `RGA_universe_score_1Mdif`, `_get_past_*`, `_calculate_differences`, `_1Mpast_rename_columns` | **初回スコープ外** | nb 未使用。バグあり。要否を確認 |
| `update_score_cumlative` | `pipelines/score_cumulative` | パスを settings に統一 |
| `port_fct_exp` | `features/factor_exposure` + `pipelines/factor_exposure` | |
| `exp_em`, `get_exp_global` | `data/exposures.exposure_global` + `features/transforms.blom_rank_normalize` | |
| `bid_to_namid`, `wd_code_change` | `data/security_master` | |
| `get_ret_usd`, `get_ret_global_daily`, `get_sret_global_daily` | `data/returns` | |
| `fret_em_daily` | `features/factor_return` + `pipelines/factor_return.run_common` | |
| `fret_nam_daily` | `data/scores.qip_monthly`, `data/exposures.tvl_raw`, `features/nam_factor_return`, `pipelines/factor_return.run_nam` | `ai_alt_score` の 3 関数を要移植 |
| `score_IC_Reb`, `ActiveWeight_score_Corr` | `features/score_monitor` + `pipelines/score_monitor` | |
| `plot_*` | `plots/*` | `plt.show()` 削除、Figure を返す |
| `cf.bm_calendar` | `data/calendar.py` | |
| `cf.monthly_calendar`, `ai_alt_score.get_pym` | `dates.previous_month` / `shift_month` | |
| `ai_alt_score.calc_blom_score` | `features/transforms.blom_score` | BLF 内の順位正規化と同一式 |
| `barra_function.gem3_exp_daily` | `data/exposures.gem3_exp_daily` | |
| `ai_alt_score.get_latest_date_factor_glb` | `data/exposures.latest_factor_glb_date` | |
| `cf.account_hold_daily` | `data/holdings` | |
| `cf.itaap_read_file` | `io/sftp.ItaapClient` | 認証情報を環境変数へ |
| `sql_connect_new.py` | `io/database` | クラス追加のみ |

## 4. CLI 設計

エントリポイント `em-weekly`（`pyproject.toml` の `[project.scripts]`）。日付は `YYYYMMDD` の int。

```
em-weekly index-return     --from 20260826 --to 20260901
em-weekly score-cumulative --to 20260901
em-weekly factor-exposure  --from 20260826
em-weekly factor-return common --from 20260130 --to 20260901
em-weekly factor-return nam    --from 20260130 --to 20260901 [--cn/--no-cn] [--q 5]
em-weekly factor-return plot   --from 20260826 --to 20260901 --inception 20260130
em-weekly score-monitor    --inception 20260130 --to 20260901 --reb 20260818 [--from 20260826] [--score-type ai|bigdata|ai70_bd30|all]
em-weekly weekly           --from 20260826 --to 20260901 --inception 20260130 --reb 20260818
```

共通オプション: `--config PATH`（既定 `config/settings.yaml`）、`--base-dir` / `--output-dir` / `--graph-dir`（出力先の上書き）、`--no-plot`、`-q`。
`weekly` はノートブック全体と同じ順序で A〜E と図を実行する。

## 5. 設定と認証情報

`config/settings.yaml`（例）:

```yaml
base_dir: /home_efs/BLF
input:
  rga_universe: input/RGA_universe/emDynExTWholdListJun2026.xlsx
  sedol_map:    input/sedol対応表/BLF_sedol変換表_202501.xlsx
  region_map:   input/region_map.xlsx
output_dir: output
graph_dir:  latest_graph
sftp:
  score_dir:   /abe/blf/score/daily
  bigdata_dir: /abe/blf/score/daily/bigdata
  qip_dir:     /k-manabe/share/qip/current/rga
accounts:
  - {cd: "0064593", until: 20241217}
  - {cd: "0065313", until: null}
benchmark: MSEM
```

環境変数（`.env` は `.gitignore` 済みの前提）: `DS_USERNAME`, `DS_PASSWORD`, `ITAAP_HOST`, `ITAAP_USERNAME`, `ITAAP_PASSWORD`, および `sql_connect_new.py` が参照する DB 用の各 `*_USERNAME` / `*_PASSWORD`。

## 6. 依存パッケージ

会社環境の許可リスト内で不足しているものを `pyproject.toml` に追加する（すべてリストに存在）:

```
scipy==1.14.1        # zscore, norm.ppf, pearsonr
scikit-learn==1.5.2  # LinearRegression
matplotlib==3.10.3
seaborn==0.13.1
openpyxl==3.1.5      # read_excel
paramiko==3.4.0      # SFTP
python-dateutil==2.8.2
pydantic==2.11.7     # settings
```

会社内製 (`pylabcore`) は pip 管理外。`DatastreamPy` は会社環境で利用可能（確認済み）。dev グループ: `pytest`。

## 7. 実施フェーズ

| Phase | 内容 | 成果物 | 自宅で検証可 |
|---|---|---|---|
| 0 | 雛形: pyproject 依存追加、`settings.py`, `constants.py`, `calendar.py`（純粋部分）, ruff 設定 | import が通る骨組み | ○ |
| 1 | `io/`: `database.py`（sql_connect_new 移植 + 4 DB 追加）、`sftp.py`、`datastream.py`、`paths.py` | 接続層 | 接続以外 ○ |
| 2 | `data/`: SQL を archive からそのまま移植し型注釈・docstring 付与。フォールバック探索を 1 箇所に集約 | 取得層 | モック ○ |
| 3 | `features/`: 純粋計算に切り出し、重複統合。単体テスト作成 | 計算層 + tests | ○ |
| 4 | `pipelines/` + `cli.py`: B → C → E の依存を尊重して組み立て | CLI が動く | △（DB 不要部分） |
| 5 | `plots/`: 3 つの累積折れ線を 1 実装に統合、Figure 返却 | 図 | ○（DataFrame から） |
| 6 | 会社環境で archive と同一日付・同一入力で CSV/PNG を突き合わせ（パリティ検証） | 検証記録 | × |
| 7 | archive 参照の削除、README 更新、`tmp.ipynb` 整理 | 完了 | ○ |

Phase 2〜3 はブロック単位（A → B → C → E → D）で進め、各ブロックごとに Phase 4 の CLI サブコマンドまで通す。D（`fret_nam_daily`）は未提供モジュールに依存するため最後に回す。

## 8. 確認事項への回答（2026-09-14）

1. `barra_function.py` と `ai_alt_score.py` を archive に追加済み。必要 4 関数は `gem3_exp_daily`（RISK_MODELS の SQL 1 本）、`get_latest_date_factor_glb`（factor_glb の SQL 1 本）、`get_pym`（前月算出）、`calc_blom_score`（Blom 順位正規化）。
2. `DatastreamPy` は会社環境で利用可能。
3. 出力先は任意指定にする。`settings.yaml` の `base_dir` と CLI の `--config` / `--output-dir` で上書きできるようにする。
4. `RGA_universe_score_1Mdif` 系は移植しない。
5. `pytest` を dev グループに追加する。
6. 環境変数名は §5 の命名で進める。

## 9. 実装状況（2026-09-14）

Phase 0〜5 を実装済み。Phase 6（会社環境でのパリティ検証）と Phase 7（archive 削除）は未実施。

### 9.1 archive からの意図的な変更点（パリティ検証時に確認すること）

| 箇所 | 変更 | 理由 |
|---|---|---|
| `fret_em_daily` の回帰 | `LinearRegression` → `cov(s, r) / var(s)` の閉形式 | 数値的に同値。sklearn 依存を計算層から外した |
| `fret_nam_daily` の `BLF_weight` 取得 | 削除 | 営業日ごとに `RGA_BM_weight` を SQL で取っていたが、結果はどこにも使われていなかった（加重版はコメントアウト済み） |
| `fret_nam_daily` の `ret` デミーン | 2 回 → 1 回 | archive は同じデミーンを 2 回適用していた。2 回目は平均 0 の系列から 0 を引くだけで結果は同じ |
| `port_fct_exp` の CSV | `index=False` | archive は無名 index 列付きで保存していた。読み側は `Category` で結合するので影響なし |
| `port_fct_exp` 内の前月末日付計算 | 削除 | 計算するだけで未使用だった |
| `account_hold_daily` の列名 | 日本語 → 英語 (`name`, `quantity`, `price`, `market_value`) | 内部利用のみ。出力 CSV には出ない |
| `update_score_cumlative` の読み込み元 | `os.getcwd()/output/...` → `settings.output_dir` | 書き込み先と統一 |
| `bm_calendar` の返り値 | `dateymd` 昇順にソート | archive は DB の返却順に依存していた |
| プロット | `plt.show()` 廃止、Figure を返す | CLI 実行のため。ノートブックでは返り値を表示すればよい |
| `_get_bigdata_factors` の遡り | 当日 + 9 日 (archive の `range(10)` と同じ) | 変更なし。明示のため記載 |

### 9.2 未検証事項

- `sns.barplot` に `hue=` を渡す形に変えた（seaborn 0.13 の非推奨警告回避）。見た目は同一のはず。
- `matplotlib.colormaps[...]` を使用（matplotlib 3.10 では `cm.get_cmap` が削除されているため。archive は 3.10 では動かない）。
- Datastream の返り値の形（`raw.values.flatten()` / `raw.index`）は archive と同じ前提。

## 10. 週次実行の効率化（2026-09-14 追加）

「データは後から改訂されうる」前提で、キャッシュと増分計算に共通の改訂ウィンドウ
(`settings.revision_window_days`, 既定 10 暦日) を設けた。

| 対策 | 実装 | 改訂への備え |
|---|---|---|
| スコアファイルのローカルキャッシュ | `io/cache.FileCache` + `data/scores.ScoreStore` | ウィンドウ内の日付は保存も参照もしない。`--refresh-cache` で全取り直し |
| スコアモニターの 3 回読み → 1 回 | `pipelines/score_monitor.load_scores` で必要日だけ読み 3 種類を計算 | 同上 |
| 共通ファクターリターンの増分化 | `pipelines/incremental.make_plan` で前回出力を再利用 | ウィンドウ内の行は再計算。`--recompute` で全期間 |
| NAM 月末エクスポージャのキャッシュ | `FileCache` kind `nam_exposure` | 同上 |
| IC・リバランス相関の増分化 | 同上 | 同上 |
| NAM D/S | 増分化しない (下記 10.1)。月末エクスポージャのキャッシュのみ | `--refresh-cache` |
| factor-exposure の universe_score 再実行 | 累積パネルから該当日の行を読む | `--recompute` で計算し直す |
| universe_score の xlsx・RGA カレンダー再読込 | `UniverseInputs` で 1 回読む | なし |
| 同一月の exposure_global 再クエリ | `data/exposures.MonthlyExposureCache` | 実行中のみ |
| Datastream / TRC の全期間取得 | 直近 400 暦日に限定 | なし |

### 10.1 増分化と archive の整合

- **NAM D/S は増分化できない。** archive の分位は「期間全体の (日 × 銘柄) をまとめて `qcut`」で境界を決めるため、
  期間の終端が伸びると過去日の値も変わる。増分計算 (過去行の再利用) は全期間計算と一致しないので、
  `run_nam` は常に全期間で集計する。月末エクスポージャ (SFTP / DB) はキャッシュするため、
  毎週の追加コストはリターンの SQL 2 本 (`exshare`, `GEM3_D_SRTN`) のみ。
  日ごとの分位化に定義を変えれば増分化できるが、archive と結果が変わるので採用していない。
- 共通ファクターリターン・IC・リバランス相関は日ごとに独立なので、同じ入力データなら増分実行と
  `--recompute` の結果は一致する (`tests/test_pipeline_incremental.py` で確認)。
- `ret_global_daily` に `map_ymd` を追加し、取得期間を絞っても bid → nam_id の変換日を全期間の開始日に固定できるようにした。
- IC の `date` 列は CSV との整合のため `YYYY-MM-DD` 文字列に統一した。
