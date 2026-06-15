# 📊 DXY – US Dollar Index Historical Data

Auto-updated daily at **6:00 AM Bangkok time (ICT, UTC+7)** via GitHub Actions.

## Files

| File | Description |
|------|-------------|
| `data/dxy.csv` | Daily OHLCV data from 2009-01-01 to present |
| `data/dxy.json` | Same data as JSON (array of objects) |
| `data/meta.json` | Last update timestamp, row count, date range |

## Data Format

### CSV (`data/dxy.csv`)
```
date,open,high,low,close,volume
2009-01-02,82.2820,82.4600,81.4810,81.5450,0
2009-01-05,81.4610,82.0440,81.2680,81.8920,0
...
```

### JSON (`data/dxy.json`)
```json
[
  {"date":"2009-01-02","open":82.282,"high":82.46,"low":81.481,"close":81.545,"volume":0},
  {"date":"2009-01-05","open":81.461,"high":82.044,"low":81.268,"close":81.892,"volume":0},
  ...
]
```

### Meta (`data/meta.json`)
```json
{
  "ticker": "DX-Y.NYB",
  "source": "Yahoo Finance",
  "last_updated": "2026-06-15T23:05:12Z",
  "rows": 4358,
  "date_from": "2009-01-02",
  "date_to": "2026-06-13"
}
```

## Schedule

The workflow runs automatically:
- **Every weekday** at **23:00 UTC** (= 06:00 Bangkok, ICT UTC+7)
- Markets are closed on weekends, so no weekend runs
- Can be triggered manually via **Actions → Update DXY Data → Run workflow**

## Data Source

Data is fetched from **Yahoo Finance** using the ticker `DX-Y.NYB`.

## Local Usage

```bash
# Run manually (requires Python 3.10+, no extra dependencies)
python scripts/fetch_dxy.py
```

## Usage Examples

### Python
```python
import json

with open("data/dxy.json") as f:
    data = json.load(f)

# Latest close
print(data[-1])
# {"date": "2026-06-13", "open": 99.73, "high": 99.88, "low": 99.73, "close": 99.81, "volume": 0}
```

### JavaScript / Node.js
```js
const data = require("./data/dxy.json");
console.log(data.at(-1)); // latest entry
```

### Pandas
```python
import pandas as pd

df = pd.read_csv("data/dxy.csv", parse_dates=["date"], index_col="date")
print(df.tail())
```
