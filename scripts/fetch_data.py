#!/usr/bin/env python3
"""
GitHub Actions用のデータ取得スクリプト。
yfinance で株価・指数を取得してテクニカル指標を計算し、update_dashboard.py が読む
scripts/tmp_data.json（スキーマは scripts/sample_data.json と同じ）を書き出す。

自動で取れないもの:
  - TSMC月次・BBレシオ・決算日・追加イベント … manual.json の値を使う
  - 信用倍率 … manual.json の credit_ratio、なければ log.csv の直近値を引き継ぐ
  - PER … log.csv の直近PERから「1株利益は次の決算まで一定」とみなして現在値で再計算
"""
import csv
import json
import math
import os
import sys

import yfinance as yf

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "scripts", "tmp_data.json")


def load(name, default):
    p = os.path.join(BASE, name)
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def rnd(x, n=2):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else round(x, n)


def fnum(s):
    try:
        return float(s) if s not in ("", None) else None
    except ValueError:
        return None


def dedupe_log():
    """同じ日付の重複行を最後の1行だけ残す（過去の手動実行で重複した分の掃除）"""
    p = os.path.join(BASE, "log.csv")
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        fields, rows = r.fieldnames, list(r)
    by_date = {}
    for row in rows:
        by_date[row["date"]] = row
    rows = [by_date[d] for d in sorted(by_date)]
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return rows


def last_value(rows, col):
    """log.csv を新しい順に見て、空でない最初の値と、その日付を返す"""
    for row in reversed(rows):
        v = fnum(row.get(col))
        if v is not None:
            return v, row["date"]
    return None, None


def hist(ticker):
    df = yf.Ticker(ticker).history(period="2y", auto_adjust=False)
    return df.dropna(subset=["Close"])


def rsi(close, period=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    return (100 - 100 / (1 + up / dn)).iloc[-1]


def jp_stock(s, log_rows, manual):
    code = s["ticker"]
    df = hist(f"{code}.T")
    c, v = df["Close"], df["Volume"]
    last, prev = c.iloc[-1], c.iloc[-2]
    vol5 = v.iloc[-6:-1].mean()

    # PER: 直近のPERと、その日の（分割調整済み）終値から1株利益を逆算
    per = None
    old_per, old_date = last_value(log_rows, f"{code}_per")
    if old_per and old_date:
        past = c[c.index.strftime("%Y-%m-%d") <= old_date]
        if len(past):
            per = last * old_per / past.iloc[-1]

    credit = (manual.get("credit_ratio") or {}).get(code)
    if credit is None:
        credit, _ = last_value(log_rows, f"{code}_credit_ratio")

    e = (manual.get("earnings") or {}).get(code, {})
    return {
        "ticker": code,
        "name": s["name"],
        "us_peers": s.get("us_peers", "―"),
        "asof": df.index[-1].strftime("%Y-%m-%d"),
        "price": rnd(last, 1),
        "chg_pct": rnd((last / prev - 1) * 100),
        "chg_yen": rnd(last - prev, 1),
        "ma25_dev": rnd((last / c.rolling(25).mean().iloc[-1] - 1) * 100),
        "ma75_dev": rnd((last / c.rolling(75).mean().iloc[-1] - 1) * 100),
        "rsi14": rnd(rsi(c)),
        "vol_ratio": rnd(v.iloc[-1] / vol5) if vol5 else None,
        "credit_ratio": rnd(credit),
        "w52_pos": rnd((last / df["High"].tail(252).max() - 1) * 100),
        "per": rnd(per),
        "next_earnings": e.get("date"),
        "next_earnings_confirmed": bool(e.get("confirmed")),
    }


def simple(ticker):
    df = hist(ticker)
    c = df["Close"]
    return df.index[-1].strftime("%Y-%m-%d"), c.iloc[-1], c.iloc[-2]


def main():
    watch = load("watchlist.json", {})
    manual = load("manual.json", {})
    log_rows = dedupe_log()
    errors = []

    stocks = []
    for s in watch.get("stocks", []):
        try:
            stocks.append(jp_stock(s, log_rows, manual))
        except Exception as ex:
            errors.append(f"{s['ticker']}: {ex}")
    if not stocks:
        sys.exit("日本株が1銘柄も取得できませんでした: " + "; ".join(errors))

    date = max(s["asof"] for s in stocks)
    for s in stocks:
        if s.pop("asof") != date:  # 取引停止などで基準日がずれた銘柄に⚠
            s["stale_fields"] = ["price", "technical", "vol_ratio", "w52_pos"]

    sector = {}
    for key, t in (("sox", "^SOX"), ("usdjpy", "JPY=X")):
        try:
            _, last, prev = simple(t)
            sector[key] = {"value": rnd(last, 2), "chg_pct": rnd((last / prev - 1) * 100)}
        except Exception as ex:
            errors.append(f"{t}: {ex}")
            sector[key] = {"value": None}
    for key in ("tsmc_yoy", "bb_ratio"):
        sector[key] = (manual.get("sector") or {}).get(key, {"value": None})

    us, us_date = [], None
    for s in watch.get("us_watchlist", []):
        try:
            d, last, prev = simple(s["ticker"])
            us_date = max(us_date or d, d)
            us.append({**s, "price": rnd(last), "chg_pct": rnd((last / prev - 1) * 100), "chg_usd": rnd(last - prev)})
        except Exception as ex:
            errors.append(f"{s['ticker']}: {ex}")

    data = {
        "date": date,
        "sector": sector,
        "stocks": stocks,
        "us_market": {"asof_date": us_date, "stocks": us},
        "extra_events": manual.get("extra_events", []),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"基準日 {date} / 日本株 {len(stocks)}銘柄 / 米国株 {len(us)}銘柄")
    for e in errors:
        print("取得失敗:", e)


if __name__ == "__main__":
    main()
