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
  - 銘柄別ウォッチ指標（東京エレクトロン・アドバンテスト・ディスコ・レーザーテック）
  - イベントカレンダー（BOJ・FOMC・各社決算・カウントダウン表示）
  - リスク管理チェックリスト／指標の見方メモ（固定コンテンツ）
- `log.csv` — セクター指標・銘柄別指標の日次記録（Excelで開けます）
- `events.json` — BOJ・FOMCなどマクロイベントの日程（**要メンテナンス**。2027年分が発表され次第追記）
- `watchlist.json` — 監視銘柄リスト。増やしたい銘柄はここに追記（`candidates_to_add`に候補を用意済み）
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
2. WebFetchで各銘柄（東京エレクトロン8035・アドバンテスト6857・ディスコ6146・レーザーテック6920）の
   指標ページを取得し、現在値・前日比・25日/75日移動平均乖離率・RSI(14)・出来高倍率・信用倍率・
   52週高値位置・PERを抽出
3. WebFetchでSOX指数・USD/JPYを取得（TSMC月次売上高・BBレシオは変化があった時だけ差し替え）
4. 上記をまとめて `scripts/tmp_data.json` に書き出す
5. `python3 scripts/update_dashboard.py scripts/tmp_data.json` を実行
6. `git add -A && git commit -m "daily update" && git push` でGitHub Pagesに反映

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

## 免責
このダッシュボードはデモトレードの練習用に指標を一覧化したものであり、投資助言ではありません。
掲載する数値・日程は情報源の発表状況により変動・誤差があり得ます。
