# BTC Cycle / DXY Regime Analytics

live : https://0xtrvkc.github.io/dynamic-btc-dxy-analytics-dashboard/
A self-contained, browser-based dashboard that analyzes Bitcoin's halving cycles against the US Dollar Index (DXY) — zone classification, peak/trough regression, forward projections, and walk-forward backtesting. Built in an SPSS-style output-viewer aesthetic: dense tables, numbered statistical blocks, minimal chrome.

No build step, no backend, no API keys. Open `index.html` in a browser and it fetches live data on its own.

## What it does

| Tab | Content |
|---|---|
| **Overview** | Current snapshot (price, ATH drawdown, DXY zone), full-history charts with real zone-band shading, cycle register, BTC/DXY return correlation |
| **Zone Days** | Days spent in each DXY regime (Trough/Weak/Neutral/Strong/Extreme) per cycle, stacked composition chart, DXY timeline with zone bands overlaid |
| **Peaks & Floors** | Naive vs. boundary-corrected peak/trough extraction, "peaks declining, floors rising" claim tested literally against the data, peak/trough regression (log scale), DXY-at-extreme trend |
| **Cycle Analysis** | Where the current cycle stands vs. every prior cycle at the *same day-offset since halving* — not calendar time. Same-point comparison table, drawdown-from-running-peak overlay, DXY path overlay |
| **Projections** | Three independent forward models (log-linear/cycle №, DXY-conditioned, decaying-multiple) for the current cycle's eventual peak and trough |
| **Backtest** | Walk-forward validation — each model refit on only the earlier cycles, graded against what actually happened. Visual actual-vs-predicted bar chart with a consensus line, plus the live (ungraded) guess for the still-open cycle |
| **Methodology** | Every modeling choice documented: data sources, halving schedule, boundary-artifact correction, zone-model derivation, regression rationale, known limitations |

Every tab can be exported as a single timestamped `.txt` report (button in the header) covering all of the above in one file.

## Data sources

Fetched live, client-side, on every page load:

- **BTC daily price**: [`dynamic-btc-analytics-dashboard/btc_daily_price.json`](https://github.com/0xtrvkc/dynamic-btc-analytics-dashboard)
- **DXY daily OHLC**: [`dynamic-btc-dxy-analytics-dashboard/data/dxy.json`](https://github.com/0xtrvkc/dynamic-btc-dxy-analytics-dashboard)

Both are fetched from `raw.githubusercontent.com`, which serves permissive CORS, so no proxy or server is needed. If a fetch fails, the dashboard falls back to the last successfully-fetched copy in memory and flags the header pill amber — it never silently substitutes placeholder numbers.

Refresh policy: fetch on load, manual refetch via the header button, and an automatic re-fetch if the in-memory cache exceeds 24 hours.

## Architecture

```
index.html          shell, design tokens (CSS), tab strip, load/error states
data_layer.js        fetch + cache + last-observation-carried-forward DXY lookup
stats_engine.js       all statistics: cycle construction, zone model, regressions,
                      projections, backtest — pure functions, no DOM access
render_views.js       HTML string builders, one function per tab
export_report.js      plain-text .txt report generator
app.js                orchestration: tabs, Chart.js wiring, custom chart plugins
chart.umd.js          vendored Chart.js v4.4.1 (no external CDN dependency)
```

The statistics engine and the rendering layer are fully separated — `stats_engine.js` never touches the DOM, and every number shown in a table or chart traces back to a single function in that file. This makes it straightforward to unit-test the math independently of the UI (see `validate_stats.py` for the Python cross-check used during development).

### The one hand-entered constant

The halving schedule is the only literal data baked into the code (`data_layer.js`):

```js
const HALVING_SCHEDULE = [
  "2012-11-28", // 1st
  "2016-07-09", // 2nd
  "2020-05-11", // 3rd
  "2024-04-20", // 4th
  "2028-03-26", // 5th (estimate)
  "2032-02-15", // 6th (estimate)
  "2036-01-10"  // 7th (estimate)
];
```

Every cycle table, zone breakdown, regression, projection, and backtest derives from this array plus whatever the two source JSON files currently contain. Appending an 8th date — or correcting a 5th/6th/7th estimate once block-time projections firm up — requires no other code changes. The same is true for the price/DXY data itself: feed in another decade of daily closes and every statistic recomputes from the live series, including the DXY zone boundaries (z-score bands recalculated from the full trailing history on every fetch, not fixed round numbers).

## Methodology notes worth knowing before reading the numbers

- **n = 3 completed cycles** is the binding constraint on every regression and projection in this dashboard. Treat R² values near 1.0 as an artifact of small sample size, not strong evidence.
- **Peak/trough extraction excludes the first 90 days post-halving from the trough search only.** A naive "lowest price in the cycle window" search returns the halving date itself in two of the three completed cycles — that's price still falling from the *previous* cycle's top, not a genuine post-halving bottom.
- **DXY zones are z-score bands** (±0.5σ / ±1.5σ around the trailing mean), not fixed thresholds — DXY's own 2009–2026 range (72.93–114.11) has drifted enough that a hardcoded number would miscalibrate over time.
- **Backtest rows only exist where they're mathematically possible.** Cycle 1 can never be a backtest target (nothing earlier to train on); Cycle 2 can't either (a 2-point trend needs 2 training cycles, and there's only 1 before it). The first cycle that can be held out and tested is Cycle 3.
- **The full-history BTC/DXY daily return correlation is ≈ −0.04** — any cycle-level relationship shown elsewhere is a slower, structural pattern, not something visible in day-to-day price action.

Full detail on every methodological choice is in the **Methodology** tab.

## Running it

No installation. Either:

- Open `index.html` directly in a browser, or
- Serve the directory with anything static (`python3 -m http.server`, GitHub Pages, etc.)

If you're hosting this on GitHub Pages, point it at the repo root — no build step, no `npm install`, no `package.json`.

## Limitations / known caveats

- Halving dates 5–7 are estimates based on Bitcoin's ~10-minute block target; actual dates have historically drifted by days-to-weeks from naive projections due to hash-rate fluctuations.
- DXY is one of several possible macro proxies (others: real yields, M2 growth, global liquidity indices). Findings here are about DXY specifically, not "macro" broadly.
- Bitcoin's halving-driven supply shock is a mechanism with no equivalent in traditional macro assets — extrapolating cycle-based thinking onto an increasingly institutionally-held, maturing asset is itself an assumption this dashboard does not independently test.
- Nothing in this dashboard is investment advice. Every projection comes with its historical backtested error rate displayed alongside it for a reason.
