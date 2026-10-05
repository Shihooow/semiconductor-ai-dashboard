# 半導体・AI ウォッチダッシュボード

## スマホで見る（公開URL）
`https://shihooow.github.io/semiconductor-ai-dashboard/`

平日の朝・夕に GitHub Actions が `index.html` / `log.csv` を自動更新し、GitHub Pagesで公開しています。
`取引判断ログ.csv`(個人の判断記録)は絶対に公開リポジトリへコピーしません（`.gitignore`対象）。


## 保存場所
`~/Claude/semiconductor-ai-dashboard/`（VIXダッシュボードと同じ `~/Claude/` 配下）

## ファイル構成
- `index.html` — 平日朝・夕に自動更新される最新状況（ブラウザで開くだけ。オフラインOK）
  - セクター先行指標（SOX指数・USD/JPY・TSMC月次売上高・BBレシオ）
  - 銘柄別ウォッチ指標（🇯🇵日本タブ＝保有想定銘柄、🇺🇸米国タブ＝先行指標として値動きのみ参考。タブで切替）
  - イベントカレンダー（BOJ・FOMC・各社決算・カウントダウン表示）
  - リスク管理チェックリスト／指標の見方メモ（固定コンテンツ）
  - ヘッダーに「更新日時」（生成した実時刻）と「基準」（データの基準日時）を表示
- `log.csv` — セクター指標・銘柄別指標・米国先行指標銘柄の日次記録（Excelで開けます）
- `events.json` — BOJ・FOMCなどマクロイベントの日程（**要メンテナンス**。2027年分が発表され次第追記）
- `watchlist.json` — 監視銘柄リスト。増やしたい銘柄はここに追記（`candidates_to_add`に候補を用意済み）。`us_watchlist`は米国タブ用の先行指標銘柄リスト（しほさんは売買せず、値動きの参考のみ）
- `manual.json` — 自動取得できない項目（TSMC月次・BBレシオ・決算日・信用倍率・追加イベント）の手動管理
- `取引判断ログ.csv` — 仕込み・決済などの判断を手動で記録する用（非公開）
- `scripts/fetch_data.py` — yfinanceでデータを取得して `scripts/tmp_data.json` を作るスクリプト（GitHub Actionsが実行）
- `scripts/template.html` — デザインテンプレート（プレースホルダー`{{...}}`を含む静的HTML）
- `scripts/update_dashboard.py` — テンプレートにデータを差し込んで`index.html`を再生成し、`log.csv`に追記するスクリプト
  - `python3 update_dashboard.py <data.json>` — data.jsonのスキーマは `scripts/sample_data.json` を参照
- `scripts/sample_data.json` — data.jsonのサンプル

## 自動更新の仕組み（GitHub Actions）
`.github/workflows/update.yml` が平日の 7:45頃（前日の東証終値＋米国市場の結果）と 16:30頃（当日の東証終値）に動きます（JST、GitHub側の混雑で数十分遅れることあり）。

1. `scripts/fetch_data.py` … yfinance で日本株・米国株・SOX・ドル円を取得し、乖離率・RSI・出来高倍率・52週高値位置を計算して `scripts/tmp_data.json` を作成
2. `scripts/update_dashboard.py scripts/tmp_data.json` … `index.html` を再生成し `log.csv` に追記
3. 変更をコミット → GitHub Pages に反映

Mac側のスケジュールタスクやトークン（`.github_token`）は不要になりました。

### 手動で更新する項目（`manual.json`）
GitHubの画面で `manual.json` を編集してコミットすれば、次回の自動更新で反映されます。
- `sector.tsmc_yoy` / `sector.bb_ratio` … TSMC月次売上高・BBレシオ（`note` は⚠のツールチップに表示）
- `earnings` … 各銘柄の次回決算日（`confirmed: true` で「見込み・要確認」表示が消える）
- `credit_ratio` … 信用倍率（例: `{"8035": 10.5}`）。書いていない銘柄は log.csv の直近値を引き継ぎ
- `extra_events` … NVIDIA決算などの追加イベント

PERは log.csv の直近PERから「1株利益は次の決算まで一定」とみなして、毎日の株価で再計算しています。決算後は `log.csv` の最新行のPERを直すと基準が更新されます。

### 今すぐ更新したいとき
Actions タブ →「Update data」→「Run workflow」。

## 判定ロジック
- 決算カウントダウンの色分け: 3日以内「警戒(赤)」、10日以内「注意(黄)」、それ以外「平常(緑)」
- 「見込み・要確認」の決算日は正式発表前の推定。manual.json側で随時更新

## 「最新の値ではない可能性」アラートマーク（⚠）
情報源のキャッシュが古い/取得できなかった項目が分かるよう、該当ラベルの横に⚠マークとツールチップ(ホバーで説明)を表示する仕組みがあります。

- 値がnull(未取得)の項目は、何もしなくても自動で⚠が付きます。
- 信用倍率は性質上つねに週次(木曜発表)更新のため、値がある限り自動で⚠が付きます（週次であることの注記）。
- それ以外で「値はあるが基準日が直近営業日とズレていそう」な項目（例: テクニカル指標だけ数日前のキャッシュだった等）は、
  data.jsonの各stock要素に `"stale_fields": ["price","technical","vol_ratio","credit_ratio","w52_pos","per"]`
  のように該当グループ名を配列で入れると⚠が付きます。複数指定可。米国タブ銘柄(us_market.stocks)は"price"のみ対応。
- セクターKPI(SOX/USD/JPY/TSMC/BBレシオ)は、`sector.<key>.value`がnull、または`note`や`stale:true`が入っていると
  自動で⚠が付きます（TSMC月次売上高・BBレシオは月次/四半期更新の性質上、noteを付けているので基本的に常時⚠が出ます）。

`scripts/fetch_data.py` は、取引停止などで基準日が他銘柄とずれた銘柄に自動で `stale_fields` を付けます。

## 免責
このダッシュボードはデモトレードの練習用に指標を一覧化したものであり、投資助言ではありません。
掲載する数値・日程は情報源の発表状況により変動・誤差があり得ます。
