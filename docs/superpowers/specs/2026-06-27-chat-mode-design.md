# Chat Mode Design — splain

**Date:** 2026-06-27

## Overview

Add a conversational chat endpoint to the existing Flask API server. `POST /chat/<session_id>` accepts a natural-language question (e.g. "Why did TSLA drop last week?"), runs a two-phase Claude pipeline — extract query params, run correlation, narrate results — and returns a prose reply. Sessions are multi-turn: conversation history and the last correlation result are cached in memory per session.

## Endpoint

```
POST /chat/<session_id>
DELETE /chat/<session_id>
```

- `session_id` is any string (UUID recommended). Unknown session IDs are auto-created on first POST.
- `DELETE` clears the session from memory.

**Request body (POST):**
```json
{"message": "Why did TSLA drop last week?"}
```

**Response (POST):**
```json
{"reply": "Tesla fell 7.3% on May 12, likely because..."}
```

**Error responses:**

| Status | Condition |
|--------|-----------|
| 400 | Missing or malformed JSON body, missing `message` field |
| 503 | `ANTHROPIC_API_KEY` not set in environment |

Stock data errors (ticker not found, missing news API key, upstream failure) are surfaced as natural-language replies rather than HTTP errors — consistent with the conversational model.

## Session State

Each session is an entry in a module-level dict keyed by `session_id`:

```python
{
    "messages": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."},
    ],
    "last_result": {
        "ticker": "TSLA",
        "from": "2026-06-20",
        "to": "2026-06-27",
        "correlations": [...]   # list of correlate.Correlation objects
    } | None
}
```

`messages` is the full conversation history passed to Claude on every turn. `last_result` is the cached output of the last successful correlation query; follow-up questions that don't imply a new data query reuse it without hitting yfinance or news APIs again.

Sessions live in memory only — lost on server restart, no TTL.

## Per-Turn Data Flow

1. Append user message to `session["messages"]`.
2. **Extract call** — send conversation history + extraction system prompt to Claude (`claude-haiku-4-5-20251001`). Response is JSON query params or `null`.
3. If non-null: call `prices.fetch_history()` → `prices.find_moves()` → `correlate.correlate()`; store result in `session["last_result"]`.
4. If null: use `session["last_result"]` as-is (may be `None` on first conversational message).
5. **Narrate call** — send conversation history + a synthetic context turn containing formatted correlation data to Claude (`claude-sonnet-4-6`). The synthetic turn is not stored in history.
6. Append assistant reply to `session["messages"]`; return `{"reply": "..."}`.

## Claude Integration

**API key:** `ANTHROPIC_API_KEY` from environment. Missing key returns 503 on the first request to any `/chat/...` route.

**Extraction call:**
- Model: `claude-haiku-4-5-20251001`
- `max_tokens`: 256
- System prompt instructs Claude to return JSON `{"ticker", "from", "to", "threshold", "window", "source"}` using today and a 90-day lookback as defaults, or `null` if the message is a follow-up or doesn't imply a new data query.

**Narration call:**
- Model: `claude-sonnet-4-6`
- `max_tokens`: 1024
- System prompt establishes Claude as a financial analyst assistant that explains stock price moves using provided correlation data concisely and grounded in the data. If no data is available, it asks the user what stock they'd like to explore.

**Prompt injection:** A synthetic `{"role": "user", "content": "<correlation data>"}` turn is prepended to the narration call's message list. Correlation data is formatted as a human-readable summary of moves and stories (not raw JSON). This turn is not stored in `session["messages"]`.

## Architecture

### New file: `splain/chat.py`

All chat logic: session state dict, `post_message(session_id, message)` orchestrator, `_extract_query()` (extraction call), `_narrate()` (narration call), `_format_correlations()` (formats result for prompt injection). Keeps `server.py` thin.

### Modified: `splain/server.py`

Add two routes delegating to `chat.py`:

```python
@app.route("/chat/<session_id>", methods=["POST"])
def post_chat(session_id): ...

@app.route("/chat/<session_id>", methods=["DELETE"])
def delete_chat(session_id): ...
```

No other changes to `server.py`.

### New file: `tests/test_chat.py`

Tests covering:
- New session auto-created on first POST
- Extraction returning a query triggers correlation and returns a reply
- Extraction returning `null` uses cached `last_result` without re-querying
- Missing `ANTHROPIC_API_KEY` returns 503
- Missing `message` field returns 400
- `DELETE` clears the session

### Modified: `pyproject.toml`

Add `anthropic` to `[project] dependencies`.

### No other files change

`cli.py`, `prices.py`, `correlate.py`, `news.py`, `finnhub.py`, `newsapi.py` are used as-is.
