#!/usr/bin/env python3
"""
DXY (US Dollar Index) Historical Data Fetcher

Sources tried in order:
  1. yfinance  — handles Yahoo Finance auth automatically (pip install yfinance)
  2. stooq.com — plain CSV, no auth, ticker: ^DXY or dxy

Run:  python scripts/fetch_dxy.py
"""

import json
import csv
import os
import sys
import time
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
START_DATE = "2009-01-01"
DATA_DIR   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
CSV_PATH   = os.path.join(DATA_DIR, "dxy.csv")
JSON_PATH  = os.path.join(DATA_DIR, "dxy.json")
META_PATH  = os.path.join(DATA_DIR, "meta.json")

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ── Source 1: yfinance (handles Yahoo auth transparently) ─────────────────────
def fetch_yfinance(start: str, end: str) -> list[dict]:
    print("  → Trying yfinance …")

    # Install if not present (GitHub Actions runner has pip)
    try:
        import yfinance as yf
    except ImportError:
        print("    Installing yfinance …")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "yfinance", "-q"],
            stdout=subprocess.DEVNULL,
        )
        import yfinance as yf

    import pandas as pd

    df = yf.download("DX-Y.NYB", start=start, end=end, progress=False, auto_adjust=True)

    if df.empty:
        raise RuntimeError("yfinance returned empty dataframe")

    # yfinance >= 0.2 returns MultiIndex columns when downloading single ticker
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    rows = []
    for ts, row in df.iterrows():
        close = row.get("Close")
        if close is None or (hasattr(close, "__float__") and str(close) == "nan"):
            continue
        rows.append({
            "date":   ts.strftime("%Y-%m-%d"),
            "open":   round(float(row["Open"]),  4) if row.get("Open")  is not None else None,
            "high":   round(float(row["High"]),  4) if row.get("High")  is not None else None,
            "low":    round(float(row["Low"]),   4) if row.get("Low")   is not None else None,
            "close":  round(float(close),        4),
            "volume": int(row.get("Volume") or 0),
        })

    rows.sort(key=lambda r: r["date"])
    print(f"  ✓ yfinance: {len(rows)} rows")
    return rows


# ── Source 2: stooq.com (plain CSV, no auth) ──────────────────────────────────
# Correct ticker for DXY on stooq is "dxy" (not dxy.f which is a futures contract)
def fetch_stooq(start: str, end: str) -> list[dict]:
    print("  → Trying stooq.com …")
    d1 = start.replace("-", "")
    d2 = end.replace("-", "")

    # stooq uses uppercase col names: Date,Open,High,Low,Close,Volume
    url = f"https://stooq.com/q/d/l/?s=dxy&d1={d1}&d2={d2}&i=d"

    def _get():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8")

    for attempt in range(1, 4):
        try:
            raw = _get()
            break
        except Exception as e:
            print(f"    [attempt {attempt}/3] {e}", file=sys.stderr)
            if attempt < 3:
                time.sleep(5 * attempt)
    else:
        raise RuntimeError("stooq: all attempts failed")

    # Detect "No data" response
    first_line = raw.strip().splitlines()[0] if raw.strip() else ""
    if first_line.lower().startswith("no data") or "date" not in first_line.lower():
        raise RuntimeError(f"stooq returned no data (response: {first_line!r})")

    rows = []
    reader = csv.DictReader(raw.splitlines())
    for row in reader:
        try:
            close_str = row.get("Close", "").strip()
            if not close_str or close_str.lower() == "null":
                continue
            rows.append({
                "date":   row["Date"].strip(),
                "open":   round(float(row["Open"]),  4),
                "high":   round(float(row["High"]),  4),
                "low":    round(float(row["Low"]),   4),
                "close":  round(float(close_str),    4),
                "volume": 0,
            })
        except (ValueError, KeyError):
            continue

    rows.sort(key=lambda r: r["date"])
    if not rows:
        raise RuntimeError("stooq: parsed 0 rows")

    print(f"  ✓ stooq: {len(rows)} rows")
    return rows


# ── Fetch with fallback ───────────────────────────────────────────────────────
def fetch(start: str, end: str) -> list[dict]:
    errors = []
    for source_fn in (fetch_yfinance, fetch_stooq):
        try:
            rows = source_fn(start, end)
            if rows:
                return rows
        except Exception as e:
            print(f"  ✗ {source_fn.__name__} failed: {e}", file=sys.stderr)
            errors.append(str(e))
    raise RuntimeError(f"All data sources failed: {'; '.join(errors)}")


# ── Persist helpers ───────────────────────────────────────────────────────────
def load_existing_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                rows.append({
                    "date":   row["date"],
                    "open":   float(row["open"])  if row.get("open")   else None,
                    "high":   float(row["high"])  if row.get("high")   else None,
                    "low":    float(row["low"])   if row.get("low")    else None,
                    "close":  float(row["close"]) if row.get("close")  else None,
                    "volume": int(row["volume"])  if row.get("volume") else 0,
                })
            except (ValueError, KeyError):
                continue
    return rows


def merge(existing: list[dict], incoming: list[dict]) -> list[dict]:
    by_date = {r["date"]: r for r in existing}
    by_date.update({r["date"]: r for r in incoming})
    return sorted(by_date.values(), key=lambda r: r["date"])


def save_csv(rows: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date","open","high","low","close","volume"])
        w.writeheader()
        w.writerows(rows)


def save_json(rows: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, separators=(",", ":"))


def save_meta(rows: list[dict], path: str, source: str = "Yahoo Finance / stooq") -> None:
    meta = {
        "ticker":       "DX-Y.NYB",
        "source":       source,
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rows":         len(rows),
        "date_from":    rows[0]["date"]  if rows else None,
        "date_to":      rows[-1]["date"] if rows else None,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    today    = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing = load_existing_csv(CSV_PATH)
    fetch_from = existing[-1]["date"] if existing else START_DATE

    print(f"📥  Fetching DXY  {fetch_from} → {today}")
    new_rows = fetch(fetch_from, today)

    merged = merge(existing, new_rows)
    save_csv(merged,  CSV_PATH)
    save_json(merged, JSON_PATH)
    save_meta(merged, META_PATH)

    added = len(merged) - len(existing)
    print(f"\n✅  Done  |  total: {len(merged)} rows  |  new: {added} rows")
    print(f"   CSV  → {CSV_PATH}")
    print(f"   JSON → {JSON_PATH}")
    print(f"   Meta → {META_PATH}")


if __name__ == "__main__":
    main()
