# em-market-weekly

新興国株式の市場レビュー用データを作成する CLI。`archive/BLF_データ作成.ipynb` をリファクタリングしたもの。

## セットアップ

```bash
uv sync
cp config/settings.example.yaml config/settings.yaml   # パスを環境に合わせて編集
cp .env.example .env                                   # 認証情報を記入する
```

`.env` はカレントディレクトリ (通常はプロジェクトルート) のものを CLI が自動で読む。
別の場所に置く場合は `--env-file PATH` で指定する。すでにシェルで設定済みの環境変数が優先される。

会社環境でのみ必要なもの: `pylabcore` (社内 DB)、`DatastreamPy`、itaap への SFTP 接続。
自宅環境では `features/` と `plots/` の単体テストのみ動く。

## 使い方

ノートブック全体に相当する週次実行:

```bash
uv run em-weekly weekly --from 20260826 --to 20260901 --inception 20260130 --reb 20260818
```

| 引数 | 意味 |
|---|---|
| `--from` | 週初 (図で強調する期間の開始日) |
| `--to` | 週末 (データ終了日) |
| `--inception` | ファクターリターン・IC の計算開始日 (図の表示開始日) |
| `--reb` | リバランス日 |

ブロック単位の実行:

```bash
uv run em-weekly index-return     --from 20260826 --to 20260901
uv run em-weekly score-cumulative --to 20260901 [--from 20260101]   # 初回のみ --from
uv run em-weekly factor-exposure  --from 20260826
uv run em-weekly factor-return common --from 20260130 --to 20260901
uv run em-weekly factor-return nam    --from 20260130 --to 20260901 --cn
uv run em-weekly factor-return plot   --from 20260826 --to 20260901 --inception 20260130
uv run em-weekly score-monitor    --inception 20260130 --to 20260901 --reb 20260818 --from 20260826
```

共通オプション (サブコマンドの前に置く):

```bash
uv run em-weekly --config other.yaml --base-dir /tmp/blf --no-plot score-cumulative --to 20260901
uv run em-weekly --env-file ~/.secrets/em.env weekly --from ... --to ... --inception ... --reb ...
```

`--base-dir` / `--output-dir` / `--graph-dir` で出力先を任意に変更できる。

## 増分計算とキャッシュ

毎週の実行で無駄な再計算をしないよう、次の仕組みがある。

- **ローカルキャッシュ** (`cache_dir`, 既定 `base_dir/cache`): itaap 上のスコアファイルや月末エクスポージャを日付ごとに保存し、2 回目以降は SFTP に接続しない。
- **増分計算**: 共通ファクターリターン、NAM ファクターリターン、IC、リバランス相関は前回出力 (`{from}_{前回の to}.csv`) を見つけて新しい日だけ計算し追記する。
- **改訂ウィンドウ** (`revision_window_days`, 既定 10 暦日): データは後から改訂されうるので、この日数以内の日付はキャッシュを信頼せず、増分計算でも計算し直す。

改訂が疑われるときは次のフラグで全部作り直せる。

```bash
uv run em-weekly --recompute --refresh-cache weekly --from ... --to ... --inception ... --reb ...
```

`--recompute` は前回出力を無視して全期間を計算し、`--refresh-cache` はキャッシュを参照せず取り直す (取り直した結果は保存される)。

## ノートブックからの利用

```python
from em_market_weekly.pipelines import factor_return, score_cumulative
from em_market_weekly.pipelines.context import Context

ctx = Context.from_config("config/settings.yaml")
panel = score_cumulative.universe_score(ctx, 20260901)
common = factor_return.run_common(ctx, 20260130, 20260901)
```

## 構成

```
src/em_market_weekly/
├── cli.py          # click コマンド
├── settings.py     # YAML + 環境変数
├── constants.py    # ファクターリスト・カテゴリ・スコア種別
├── dates.py        # 日付ヘルパー (純粋関数)
├── io/             # DB (pylabcore) / SFTP / Datastream / 出力パス
├── data/           # SQL・ファイル → DataFrame
├── features/       # 純粋計算 (I/O なし)
├── plots/          # DataFrame → Figure
└── pipelines/      # data → features → 保存 → plots
```

詳細は [docs/refactoring_plan.md](docs/refactoring_plan.md) を参照。

## 開発

```bash
uv run ruff check --select I --fix src tests
uv run ruff format src tests
uv run pytest
```
