#!/usr/bin/env python3
"""
DXY (US Dollar Index) Historical Data Fetcher
Fetches daily OHLCV data from 2009 to present.

Sources (tried in order):
  1. Yahoo Finance  – DX-Y.NYB  (primary, needs crumb+cookie handshake)
  2. stooq.com      – dxy.f      (fallback, plain CSV)
"""

import json
import csv
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
START_DATE = "2009-01-01"
TICKER_YF  = "DX-Y.NYB"
TICKER_STOOQ = "dxy.f"

DATA_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
CSV_PATH  = os.path.join(DATA_DIR, "dxy.csv")
JSON_PATH = os.path.join(DATA_DIR, "dxy.json")
META_PATH = os.path.join(DATA_DIR, "meta.json")

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def date_to_unix(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def retry(fn, attempts=3, wait=5):
    for i in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:
            print(f"  [attempt {i}/{attempts}] {e}", file=sys.stderr)
            if i < attempts:
                time.sleep(wait * i)
    raise RuntimeError(f"All {attempts} attempts failed")


# ── Source 1: Yahoo Finance (crumb + cookie) ──────────────────────────────────
def _yahoo_crumb_and_cookie() -> tuple[str, str]:
    """Return (crumb, cookie_header) by hitting the consent page first."""
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    # Step 1 – hit the chart page to get session cookies
    req = urllib.request.Request(
        f"https://finance.yahoo.com/quote/{TICKER_YF}/history/",
        headers={"User-Agent": UA},
    )
    with opener.open(req, timeout=15):
        pass  # we just need the cookies

    # Step 2 – fetch crumb
    crumb_req = urllib.request.Request(
        "https://query1.finance.yahoo.com/v1/test/getcrumb",
        headers={"User-Agent": UA},
    )
    with opener.open(crumb_req, timeout=10) as r:
        crumb = r.read().decode("utf-8").strip()

    # Serialize cookies for direct use
    cookie_str = "; ".join(f"{c.name}={c.value}" for c in jar)
    return crumb, cookie_str


def fetch_yahoo(start: str, end: str) -> list[dict]:
    print("  → Trying Yahoo Finance …")
    crumb, cookie = retry(_yahoo_crumb_and_cookie)

    p1, p2 = date_to_unix(start), date_to_unix(end)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{TICKER_YF}"
        f"?period1={p1}&period2={p2}&interval=1d"
        f"&events=history&crumb={urllib.parse.quote(crumb)}"
    )

    def _get():
        req = urllib.request.Request(
            url,
            headers={"User-Agent": UA, "Cookie": cookie},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    raw    = retry(_get)
    result = raw["chart"]["result"][0]
    ts     = result["timestamp"]
    q      = result["indicators"]["quote"][0]

    rows = []
    for i, stamp in enumerate(ts):
        close = q["close"][i]
        if close is None:
            continue
        rows.append({
            "date":   datetime.fromtimestamp(stamp, tz=timezone.utc).strftime("%Y-%m-%d"),
            "open":   round(q["open"][i],  4) if q["open"][i]  is not None else None,
            "high":   round(q["high"][i],  4) if q["high"][i]  is not None else None,
            "low":    round(q["low"][i],   4) if q["low"][i]   is not None else None,
            "close":  round(close,         4),
            "volume": q["volume"][i] or 0,
        })
    rows.sort(key=lambda r: r["date"])
    print(f"  ✓ Yahoo: {len(rows)} rows")
    return rows


# ── Source 2: stooq.com (plain CSV, no auth) ─────────────────────────────────
def fetch_stooq(start: str, end: str) -> list[dict]:
    print("  → Trying stooq.com …")
    d1 = start.replace("-", "")
    d2 = end.replace("-", "")
    url = (
        f"https://stooq.com/q/d/l/"
        f"?s={TICKER_STOOQ}&d1={d1}&d2={d2}&i=d"
    )

    def _get():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8")

    raw  = retry(_get)
    rows = []
    reader = csv.DictReader(raw.splitlines())
    for row in reader:
        try:
            rows.append({
                "date":   row["Date"],
                "open":   round(float(row["Open"]),  4),
                "high":   round(float(row["High"]),  4),
                "low":    round(float(row["Low"]),   4),
                "close":  round(float(row["Close"]), 4),
                "volume": 0,
            })
        except (ValueError, KeyError):
            continue
    rows.sort(key=lambda r: r["date"])
    print(f"  ✓ stooq: {len(rows)} rows")
    return rows


# ── Fetch with fallback ───────────────────────────────────────────────────────
def fetch(start: str, end: str) -> list[dict]:
    for source in (fetch_yahoo, fetch_stooq):
        try:
            rows = source(start, end)
            if rows:
                return rows
        except Exception as e:
            print(f"  ✗ Source failed: {e}", file=sys.stderr)
    raise RuntimeError("All data sources failed.")


# ── Persist helpers ───────────────────────────────────────────────────────────
def load_existing_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "date":   row["date"],
                "open":   float(row["open"])  if row.get("open")   else None,
                "high":   float(row["high"])  if row.get("high")   else None,
                "low":    float(row["low"])   if row.get("low")    else None,
                "close":  float(row["close"]) if row.get("close")  else None,
                "volume": int(row["volume"])  if row.get("volume") else 0,
            })
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


def save_meta(rows: list[dict], path: str) -> None:
    meta = {
        "ticker":       TICKER_YF,
        "source":       "Yahoo Finance / stooq.com",
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

    # Only fetch from the last known date onwards (incremental after first run)
    fetch_from = existing[-1]["date"] if existing else START_DATE
    print(f"📥  Fetching DXY from {fetch_from} → {today}")

    new_rows = fetch(fetch_from, today)
    merged   = merge(existing, new_rows)

    save_csv(merged,  CSV_PATH)
    save_json(merged, JSON_PATH)
    save_meta(merged, META_PATH)

    added = len(merged) - len(existing)
    print(f"\n✅  Done  |  total rows: {len(merged)}  |  new rows: {added}")
    print(f"   CSV  → {CSV_PATH}")
    print(f"   JSON → {JSON_PATH}")
    print(f"   Meta → {META_PATH}")


if __name__ == "__main__":
    main()
