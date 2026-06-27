# splain — agent guidance

## Purpose
Correlate historical stock price moves with contemporary news stories.
CLI: `uv run splain <TICKER> [--from DATE] [--to DATE] [--threshold PCT] [--window DAYS]`

## Stack
- **uv** for all dependency management (`uv add`, `uv sync --extra dev`, `uv run`)
- **yfinance** for OHLCV price history (no auth required)
- **NewsAPI** (`newsapi.org`) for news stories — requires `NEWSAPI_KEY`
- **typer** for CLI
- **pytest** for tests

## Environment
API keys live in `.env` at the project root. The CLI loads it automatically via `python-dotenv`. Never require the user to export env vars manually.

```
NEWSAPI_KEY=...
```

## Key files
| File | Role |
|------|------|
| `splain/prices.py` | `fetch_history()` + `find_moves()` — yfinance wrapper, MultiIndex flattening |
| `splain/news.py` | `fetch_stories()` — NewsAPI wrapper, graceful 426 handling (free tier limit) |
| `splain/correlate.py` | `correlate()` — pairs each `PriceMove` with its `NewsStory` list |
| `splain/cli.py` | Typer app, loads `.env`, degrades gracefully when no API key |
| `tests/` | Unit tests with mocked HTTP — no live network calls in tests |

## Style
- Plain text output only — no color, no Rich markup, no bold. `print()` not `console.print()`.
- Typer initialized with `rich_markup_mode=None` to keep `--help` plain.

## Conventions
- NewsAPI free tier only covers ~1 month back — return `[]` silently on 426, don't crash
- If no `NEWSAPI_KEY` is available, show price moves only with a yellow notice; do not error
- Import modules, not things in modules: `import datetime` not `from datetime import date`
- Always use `from pkg import mod` for nested modules: `from unittest import mock` not `import unittest.mock`
- This applies universally: stdlib, third-party, and internal (`from splain import prices`)
- NEVER use unittest.mock: it encourages bad test habits

## Running
```bash
uv sync --extra dev       # install deps
uv run splain TSLA        # last 90 days, threshold 3%
uv run pytest -v          # run tests
```
