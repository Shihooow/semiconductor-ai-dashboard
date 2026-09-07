#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
半導体・AIウォッチダッシュボード 自動更新スクリプト
======================================================
VIXダッシュボード(scripts/update_dashboard.py)と同じ設計思想:
  - データ取得(WebFetch等)はこのスクリプトの外(スケジュールタスク側)で行う
  - このスクリプトは「その日の数値」を受け取って
      1) log.csv に1行追記
      2) template.html にデータを差し込んで index.html を再生成
    するだけの、依存ライブラリ無し(標準ライブラリのみ)のレンダラー

使い方:
    python3 update_dashboard.py <data.json>

<data.json> のスキーマは README.md 参照。
毎朝のスケジュールタスクは、次の手順で <data.json> を作ってからこのスクリプトを呼ぶ想定:
    1. WebFetch で各銘柄の指標ページ(例: kabutan.jp の株価指標タブ)を取得し、
       現在値/前日比/25日・75日移動平均乖離率/RSI(14)/出来高倍率/信用倍率/52週高値位置/PERを抽出
    2. WebFetch で SOX指数・USD/JPY を取得
    3. TSMC月次売上高・BBレシオは月次/四半期更新なので、変化があった日だけ差し替え
    4. 上記をまとめた JSON を書き出し、このスクリプトを実行
    5. git add / commit / push (リモートは事前に fine-grained PAT 付きで設定済みの想定)
"""

import sys
import csv
import json
import os
from datetime import date, datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(SCRIPTS_DIR, "template.html")
OUTPUT_PATH = os.path.join(BASE_DIR, "index.html")
LOG_PATH = os.path.join(BASE_DIR, "log.csv")
EVENTS_PATH = os.path.join(BASE_DIR, "events.json")
WATCHLIST_PATH = os.path.join(BASE_DIR, "watchlist.json")

STOCK_COLOR_VARS = ["stock-tel", "stock-adv", "stock-dsc", "stock-lzt"]
# 5銘柄目以降はこの並びを繰り返す(色が重複するが致命的ではない)


# ---------------------------------------------------------------------------
# 汎用ヘルパー
# ---------------------------------------------------------------------------

def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def delta_class(v):
    if v is None:
        return "flat"
    return "up" if v > 0 else ("down" if v < 0 else "flat")


def fmt_pct(v, digits=1):
    if v is None:
        return "―"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.{digits}f}%"


def fmt_num(v, digits=1):
    if v is None:
        return "―"
    return f"{v:,.{digits}f}"


def fmt_yen(v):
    if v is None:
        return "―"
    return f"¥{v:,.0f}"


def days_until(date_str, today):
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None
    return (d - today).days


def cd_level(days):
    if days is None or days < 0:
        return None
    if days <= 3:
        return "crit"
    if days <= 10:
        return "warn"
    return "good"


def cd_label(days):
    if days is None:
        return "未定"
    if days < 0:
        return "終了"
    if days == 0:
        return "本日"
    return f"{days}日"


# ---------------------------------------------------------------------------
# セクションビルダー
# ---------------------------------------------------------------------------

SECTOR_META = {
    "sox": {
        "label": "SOX指数（フィラデルフィア半導体指数）",
        "desc": "米国半導体株の集合指数。前日の米国市場の流れが翌朝の東エレ・アドバンテストの寄付きに影響しやすい。",
        "fmt": lambda v: fmt_num(v, 1),
    },
    "usdjpy": {
        "label": "USD/JPY",
        "desc": "輸出比率が高い装置・検査メーカーが中心。円安は業績押し上げ要因、急な円高は要警戒。",
        "fmt": lambda v: fmt_num(v, 2),
    },
    "tsmc_yoy": {
        "label": "TSMC 月次売上高（前年同月比）",
        "desc": "世界の半導体需要の先行指標。台湾積体電路製造が毎月10日前後に発表。AI向け需要の体温計。",
        "fmt": lambda v: fmt_pct(v, 0),
    },
    "bb_ratio": {
        "label": "北米半導体製造装置 BBレシオ",
        "desc": "受注額÷出荷額。SEMIが四半期ごとに発表。1.00超が受注超過＝装置株に追い風のサイン。",
        "fmt": lambda v: fmt_num(v, 2),
    },
}
SECTOR_ORDER = ["sox", "usdjpy", "tsmc_yoy", "bb_ratio"]


def build_kpi_tiles(sector):
    tiles = []
    for key in SECTOR_ORDER:
        meta = SECTOR_META[key]
        entry = sector.get(key, {})
        value = entry.get("value")
        chg = entry.get("chg_pct")
        dclass = delta_class(chg)
        chg_text = fmt_pct(chg, 1) if chg is not None else entry.get("note", "―")
        tiles.append(f'''
      <div class="kpi">
        <div class="label">{meta['label']}</div>
        <div class="value-row"><span class="value">{meta['fmt'](value)}</span><span class="delta {dclass}">{chg_text}</span></div>
        <div class="desc">{meta['desc']}</div>
      </div>''')
    return "\n".join(tiles)


def build_stock_cards(stocks, today):
    cards = []
    for i, s in enumerate(stocks):
        color = STOCK_COLOR_VARS[i % len(STOCK_COLOR_VARS)]
        chg_pct = s.get("chg_pct")
        chg_class = "good" if (chg_pct or 0) >= 0 else "critical"
        chg_sign = "+" if (chg_pct or 0) >= 0 else ""
        chg_yen = s.get("chg_yen")
        chg_yen_txt = f"({chg_sign}{chg_yen:,.0f})" if chg_yen is not None else ""

        ne_date = s.get("next_earnings")
        ne_days = days_until(ne_date, today) if ne_date else None
        ne_level = cd_level(ne_days) or "good"
        ne_confirmed = s.get("next_earnings_confirmed", False)
        ne_footnote = "次回決算まで" if ne_confirmed else "次回決算まで（見込み・要確認）"

        cards.append(f'''
      <div class="stock-card" style="--accent-line:var(--{color})">
        <div class="head">
          <div class="name-block">
            <div class="ticker">{s['ticker']}.T</div>
            <div class="name">{s['name']}</div>
          </div>
          <div class="price-block">
            <div class="price">{fmt_yen(s.get('price'))}</div>
            <div class="change" style="color:var(--{chg_class})">{chg_sign}{fmt_pct(chg_pct)} {chg_yen_txt}</div>
          </div>
        </div>
        <div class="body">
          <div class="metric-row"><span class="m-label">25日線 / 75日線 乖離率</span><span class="m-value">{fmt_pct(s.get('ma25_dev'))} / {fmt_pct(s.get('ma75_dev'))}</span></div>
          <div class="metric-row"><span class="m-label">RSI(14)</span><span class="m-value">{fmt_num(s.get('rsi14'))}</span></div>
          <div class="metric-row"><span class="m-label">出来高（対5日平均）</span><span class="m-value">{fmt_num(s.get('vol_ratio'))}倍</span></div>
          <div class="metric-row"><span class="m-label">信用倍率（買い残÷売り残）</span><span class="m-value">{fmt_num(s.get('credit_ratio'))}倍</span></div>
          <div class="metric-row"><span class="m-label">52週高値からの位置</span><span class="m-value">{fmt_pct(s.get('w52_pos'))}</span></div>
          <div class="metric-row"><span class="m-label">PER（同業比較）</span><span class="m-value">{fmt_num(s.get('per'))}倍</span></div>
          <div class="metric-row"><span class="m-label">米国連動参考銘柄</span><span class="m-value">{s.get('us_peers', '―')}</span></div>
        </div>
        <div class="footnote">
          <span class="fx-note">{ne_footnote}</span>
          <span class="cd-pill {ne_level}" data-cd="{ne_date or ''}">{cd_label(ne_days)}</span>
        </div>
      </div>''')
    return "\n".join(cards)


def build_calendar_rows(events, today):
    # 直近3日以内に終わったものまでは表示、それより古いものは除外
    visible = []
    for e in events:
        d = days_until(e["date"], today)
        if d is None or d < -3:
            continue
        visible.append((d, e))
    visible.sort(key=lambda x: x[0])

    rows = []
    for d, e in visible:
        cat = e.get("category", "macro")
        cat_label = "マクロ" if cat == "macro" else "決算"
        try:
            _d = datetime.strptime(e["date"], "%Y-%m-%d").date()
            default_disp = f"{_d.month:02d}/{_d.day:02d}"
        except ValueError:
            default_disp = e["date"]
        date_disp = e.get("date_disp", default_disp)
        rows.append(
            f'<tr data-date="{e["date"]}"><td class="date">{date_disp}</td>'
            f'<td>{e["label"]}</td>'
            f'<td><span class="cat-tag {cat}">{cat_label}</span></td>'
            f'<td class="cd-cell"></td></tr>'
        )
    return "\n        ".join(rows)


def build_stock_chips(stocks):
    chips = []
    for i, s in enumerate(stocks):
        color = STOCK_COLOR_VARS[i % len(STOCK_COLOR_VARS)]
        chips.append(
            f'<span class="stock-chip" style="color:var(--{color}); border-color:var(--{color});">'
            f'{s["ticker"]} {s["name"]}</span>'
        )
    return "\n        ".join(chips)


# ---------------------------------------------------------------------------
# ログ (log.csv) 追記
# ---------------------------------------------------------------------------

LOG_FIELDS_BASE = ["date", "sox", "sox_chg", "usdjpy", "usdjpy_chg", "tsmc_yoy", "bb_ratio"]


def append_log(data):
    file_exists = os.path.exists(LOG_PATH)
    row = {
        "date": data["date"],
        "sox": data["sector"].get("sox", {}).get("value"),
        "sox_chg": data["sector"].get("sox", {}).get("chg_pct"),
        "usdjpy": data["sector"].get("usdjpy", {}).get("value"),
        "usdjpy_chg": data["sector"].get("usdjpy", {}).get("chg_pct"),
        "tsmc_yoy": data["sector"].get("tsmc_yoy", {}).get("value"),
        "bb_ratio": data["sector"].get("bb_ratio", {}).get("value"),
    }
    fieldnames = list(LOG_FIELDS_BASE)
    for s in data["stocks"]:
        prefix = s["ticker"]
        for key in ["price", "chg_pct", "ma25_dev", "ma75_dev", "rsi14", "vol_ratio", "credit_ratio", "w52_pos", "per"]:
            colname = f"{prefix}_{key}"
            fieldnames.append(colname)
            row[colname] = s.get(key)

    # 既存ファイルがあれば列構成を維持しつつ追記(新しい銘柄が増えた場合はヘッダーを書き直す)
    existing_rows = []
    existing_fields = []
    if file_exists:
        with open(LOG_PATH, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            existing_fields = reader.fieldnames or []
            existing_rows = list(reader)

    merged_fields = existing_fields[:]
    for fn in fieldnames:
        if fn not in merged_fields:
            merged_fields.append(fn)

    # 同じ日付の行がすでにあれば上書き(同日に複数回実行した場合の安全策)
    existing_rows = [r for r in existing_rows if r.get("date") != row["date"]]
    existing_rows.append(row)
    existing_rows.sort(key=lambda r: r.get("date", ""))

    with open(LOG_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=merged_fields)
        writer.writeheader()
        for r in existing_rows:
            writer.writerow({k: r.get(k, "") for k in merged_fields})


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("使い方: python3 update_dashboard.py <data.json>", file=sys.stderr)
        sys.exit(1)

    data_path = sys.argv[1]
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    today = datetime.strptime(data["date"], "%Y-%m-%d").date()

    macro_events = load_json(EVENTS_PATH, [])
    extra_events = data.get("extra_events", [])

    earnings_events = []
    for s in data["stocks"]:
        ne = s.get("next_earnings")
        if ne:
            label = s.get("earnings_label") or f"{s['name']} 決算発表" + ("" if s.get("next_earnings_confirmed") else "（見込み・要確認）")
            earnings_events.append({"date": ne, "label": label, "category": "earnings"})

    all_events = macro_events + extra_events + earnings_events

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    replacements = {
        "{{BADGE_CLASS}}": "live",
        "{{BADGE_TEXT}}": "● 自動更新（前日終値ベース）",
        "{{ASOF_TEXT}}": f"基準日: {data['date']}",
        "{{STOCK_CHIPS}}": build_stock_chips(data["stocks"]),
        "{{KPI_TILES}}": build_kpi_tiles(data["sector"]),
        "{{CALENDAR_ROWS}}": build_calendar_rows(all_events, today),
        "{{STOCK_CARDS}}": build_stock_cards(data["stocks"], today),
        "{{FOOTER_NOTES}}": (
            "<p>※ データ取得元: Yahoo Finance / 各社IRサイト（毎朝スケジュールタスクが自動取得・生成）。"
            "「見込み・要確認」表示の決算日は正式発表前の推定です。</p>"
            "<p>取引判断ログ.csv は自動公開されません（.gitignore対象）。"
            "このダッシュボードはデモトレードの練習用であり、投資助言ではありません。</p>"
        ),
    }

    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    append_log(data)

    print(f"更新完了: {OUTPUT_PATH}")
    print(f"ログ追記: {LOG_PATH}")


if __name__ == "__main__":
    main()
