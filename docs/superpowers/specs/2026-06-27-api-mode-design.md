# API Mode Design — splain

**Date:** 2026-06-27

## Overview

Add an HTTP server mode to the `splain` CLI. Running `splain --api` starts a Flask server on `127.0.0.1` that exposes the same stock-move/news-correlation functionality as the CLI, returning structured JSON instead of plain text.

## CLI Interface

Two new options are added to the existing `splain` command:

```
splain --api            # start server on 127.0.0.1:5000
splain --api --port 8080
```

- `ticker` becomes optional when `--api` is set (tickers are supplied per-request)
- All other existing options (`--source`, `--threshold`, etc.) are unaffected

## Endpoint

```
GET /correlations/<TICKER>
```

**Query parameters** (all optional, same defaults as CLI):

| Parameter   | Default        | Description                        |
|-------------|----------------|------------------------------------|
| `from`      | today − 90d    | Start date (YYYY-MM-DD)            |
| `to`        | today          | End date (YYYY-MM-DD)              |
| `threshold` | 2.0            | Minimum absolute move (%)          |
| `window`    | 1              | News search window ±days per move  |
| `source`    | finnhub        | News source: `finnhub`, `newsapi`, `none` |

## JSON Response Shape

```json
{
  "ticker": "TSLA",
  "from": "2026-03-28",
  "to": "2026-06-27",
  "moves": [
    {
      "date": "2026-05-12",
      "open": 321.50,
      "close": 298.10,
      "pct_change": -7.3,
      "volume": 123456789,
      "stories": [
        {
          "title": "Tesla misses delivery estimates",
          "source": "Reuters",
          "published_at": "2026-05-12T14:30:00+00:00",
          "url": "https://example.com/article",
          "description": "Tesla reported lower than expected deliveries..."
        }
      ]
    }
  ]
}
```

## Error Handling

All errors return JSON `{"error": "<message>"}` with an appropriate HTTP status:

| Status | Condition                                              |
|--------|--------------------------------------------------------|
| 400    | Missing ticker, bad date format, unknown source value  |
| 404    | Ticker not found (yfinance returns no data)            |
| 503    | API key missing or upstream request fails              |

## Architecture

### New file: `splain/server.py`

Contains the Flask `app` object and the `GET /correlations/<ticker>` route handler. Responsibilities:
- Parse and validate query parameters
- Call existing `prices.fetch_history()`, `prices.find_moves()`, and `correlate.correlate()`
- Serialize results to JSON
- Map exceptions to HTTP status codes

API keys are read from the environment. `dotenv.load_dotenv()` is called in `cli.py` before `server.run()`, so `.env` is already loaded.

No authentication on the server itself — localhost-only binding is the security boundary.

### Changes to `splain/cli.py`

- Add `--api` flag (boolean, default False)
- Add `--port` option (integer, default 5000)
- Make `ticker` argument optional (required only when `--api` is False)
- When `--api` is set: call `server.run(host="127.0.0.1", port=port)` instead of the analysis flow

### No other files change

`prices.py`, `correlate.py`, `news.py`, `finnhub.py`, `newsapi.py` are used as-is by `server.py`.
