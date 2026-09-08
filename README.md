# 半導体・AI ウォッチダッシュボード

## スマホで見る（公開URL）
GitHubリポジトリ作成後、GitHub Pagesを有効化すると
`https://shihooow.github.io/semiconductor-ai-dashboard/` のようなURLで見られるようになります（VIXダッシュボードと同じ形）。

毎朝の自動更新のたびに、GitHubリポジトリ `semiconductor-ai-dashboard`(Public)へ
`index.html` / `log.csv` を自動pushし、GitHub Pagesで公開する設計です。
`取引判断ログ.csv`(個人の判断記録)は絶対に公開リポジトリへコピーしません（`.gitignore`対象）。

pushに使うfine-grainedトークンは、VIXダッシュボードと同じやり方で
このフォルダ直下の `.github_token` に平文保存する想定です（`.gitignore`対象）。

## 保存場所
`~/Claude/semiconductor-ai-dashboard/`（VIXダッシュボードと同じ `~/Claude/` 配下）

## ファイル構成
- `index.html` — 毎朝自動更新される最新状況（ブラウザで開くだけ。オフラインOK）
  - セクター先行指標（SOX指数・USD/JPY・TSMC月次売上高・BBレシオ）
  - 銘柄別ウォッチ指標（🇯🇵日本タブ＝保有想定銘柄、🇺🇸米国タブ＝先行指標として値動きのみ参考。タブで切替）
  - イベントカレンダー（BOJ・FOMC・各社決算・カウントダウン表示）
  - リスク管理チェックリスト／指標の見方メモ（固定コンテンツ）
  - ヘッダーに「更新日時」（生成した実時刻）と「基準」（データの基準日時）を表示
- `log.csv` — セクター指標・銘柄別指標・米国先行指標銘柄の日次記録（Excelで開けます）
- `events.json` — BOJ・FOMCなどマクロイベントの日程（**要メンテナンス**。2027年分が発表され次第追記）
- `watchlist.json` — 監視銘柄リスト。増やしたい銘柄はここに追記（`candidates_to_add`に候補を用意済み）。`us_watchlist`は米国タブ用の先行指標銘柄リスト（しほさんは売買せず、値動きの参考のみ）
- `取引判断ログ.csv` — 仕込み・決済などの判断を手動で記録する用（非公開）
- `scripts/template.html` — デザインテンプレート（プレースホルダー`{{...}}`を含む静的HTML）
- `scripts/update_dashboard.py` — テンプレートにデータを差し込んで`index.html`を再生成し、`log.csv`に追記するスクリプト
  - `python3 update_dashboard.py <data.json>` — data.jsonのスキーマは `scripts/sample_data.json` を参照
- `scripts/sample_data.json` — data.jsonのサンプル（初回セットアップ用の暫定値。初回自動実行で実データに置き換わる）

## 自動更新の仕組み（VIXダッシュボードとの違い）
VIXはCboeから数値をそのまま取得できましたが、個別株は「25日移動平均乖離率」「RSI(14)」
「信用倍率」など計算済みの指標を提供しているサイト（例: 株探 kabutan.jp の株価指標タブ）から
まとめて読み取るのが現実的です。想定フロー:

1. 平日 朝6:30頃、スケジュールタスクが起動
2. WebFetchで`watchlist.json`の各銘柄の指標ページを取得し、現在値・前日比・25日/75日移動平均乖離率・
   RSI(14)・出来高倍率・信用倍率・52週高値位置・PERを抽出
3. WebFetchでSOX指数・USD/JPYを取得（TSMC月次売上高・BBレシオは変化があった時だけ差し替え）
4. WebFetchで`watchlist.json`の`us_watchlist`（米国タブ用・8銘柄）の現在値・前日比を取得
   （こちらは日本株のような詳細テクニカル指標は不要。先行指標として値動きだけ分かればよい）
5. 上記をまとめて `scripts/tmp_data.json` に書き出す（`us_market.asof_date`には取得した米国市場の
   取引日を入れる）
6. `python3 scripts/update_dashboard.py scripts/tmp_data.json` を実行
7. `git add -A && git commit -m "daily update" && git push` でGitHub Pagesに反映

## セットアップ手順（しほさんにお願いしたい部分）
このスクリプト・フォルダは用意できましたが、以下の3点はGitHub側の認証が必要なため
しほさんの操作をお願いします（VIXダッシュボードの時と同じ手順です）。

1. https://github.com/new で新しいリポジトリ `semiconductor-ai-dashboard` を作成（Public、READMEなし）
2. リポジトリの Settings → Pages で公開設定（Branch: main, フォルダ: / (root)）
3. https://github.com/settings/personal-access-tokens で、このリポジトリだけに
   スコープを絞った fine-grained トークン（Contents: Read and write）を発行
4. ターミナルで以下を実行（`<TOKEN>` は発行したトークンに置き換え）:
   ```
   cd ~/Claude/semiconductor-ai-dashboard
   git remote add origin https://<TOKEN>@github.com/Shihooow/semiconductor-ai-dashboard.git
   git branch -M main
   git push -u origin main
   ```

上記が終わったら教えてください。スケジュールタスク（毎朝6:30・平日）を設定します。

## 判定ロジック
- 決算カウントダウンの色分け: 3日以内「警戒(赤)」、10日以内「注意(黄)」、それ以外「平常(緑)」
- 「見込み・要確認」の決算日は正式発表前の推定。events.json/watchlist.json側で随時更新

## 「最新の値ではない可能性」アラートマーク（⚠）
情報源のキャッシュが古い/取得できなかった項目が分かるよう、該当ラベルの横に⚠マークとツールチップ(ホバーで説明)を表示する仕組みがあります。

- 値がnull(未取得)の項目は、何もしなくても自動で⚠が付きます。
- 信用倍率は性質上つねに週次(木曜発表)更新のため、値がある限り自動で⚠が付きます（週次であることの注記）。
- それ以外で「値はあるが基準日が直近営業日とズレていそう」な項目（例: テクニカル指標だけ数日前のキャッシュだった等）は、
  data.jsonの各stock要素に `"stale_fields": ["price","technical","vol_ratio","credit_ratio","w52_pos","per"]`
  のように該当グループ名を配列で入れると⚠が付きます。複数指定可。米国タブ銘柄(us_market.stocks)は"price"のみ対応。
- セクターKPI(SOX/USD/JPY/TSMC/BBレシオ)は、`sector.<key>.value`がnull、または`note`や`stale:true`が入っていると
  自動で⚠が付きます（TSMC月次売上高・BBレシオは月次/四半期更新の性質上、noteを付けているので基本的に常時⚠が出ます）。

毎朝のスケジュールタスクは、WebFetchで取得した各指標の実際の基準日を確認し、当日の基準日(data.jsonの`date`)と
ズレている項目があれば`stale_fields`に追記してからdata.jsonを書き出してください。

## 免責
このダッシュボードはデモトレードの練習用に指標を一覧化したものであり、投資助言ではありません。
掲載する数値・日程は情報源の発表状況により変動・誤差があり得ます。
