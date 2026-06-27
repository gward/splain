"""Multi-turn chat over stock correlation data using Claude."""

import datetime
import json
import os
from typing import Any

import anthropic

from splain import correlate, finnhub, news, newsapi, prices

_sessions: dict[str, dict[str, Any]] = {}

_SOURCES: dict[str, tuple[news.FetchFunction, str]] = {
    "newsapi": (newsapi.fetch_stories, "NEWSAPI_KEY"),
    "finnhub": (finnhub.fetch_stories, "FINNHUB_KEY"),
}

_EXTRACT_SYSTEM = (
    "You are a query parser for a stock analysis tool. "
    "Given a conversation, extract the stock query the user is asking about and return it as JSON: "
    '{"ticker": "TSLA", "from": "YYYY-MM-DD", "to": "YYYY-MM-DD", "threshold": 2.0, "window": 1, "source": "finnhub"}. '
    "Use today's date as the end date and 90 days prior as the start date by default. "
    'Valid source values: "finnhub", "newsapi", "none". Default: "finnhub". '
    "Return null (the JSON literal) if the message is a follow-up that does not require fetching new data. "
    "Return ONLY the JSON object or null — no other text."
)

_NARRATE_SYSTEM = (
    "You are a financial analyst assistant. "
    "Explain stock price moves concisely and directly, grounded in the provided data. "
    "If no stock data is available, say so and ask the user what stock they would like to explore.\n\n"
    "{data_section}"
)


def _get_or_create(session_id: str) -> dict[str, Any]:
    if session_id not in _sessions:
        _sessions[session_id] = {"messages": [], "last_result": None}
    return _sessions[session_id]


def clear_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


def _extract_query(messages: list[dict[str, str]]) -> dict[str, Any] | None:
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=_EXTRACT_SYSTEM,
        messages=messages,
    )
    text = resp.content[0].text.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if parsed is None or isinstance(parsed, dict):
        return parsed
    return None


def _format_result(result: dict[str, Any]) -> str:
    lines = [f"Ticker: {result['ticker']}  Period: {result['from']} to {result['to']}"]
    for corr in result["correlations"]:
        m = corr.move
        sign = "+" if m.pct_change > 0 else ""
        lines.append(
            f"\n{sign}{m.pct_change:.1f}%  {m.date}  open={m.open:.2f}  close={m.close:.2f}  volume={m.volume:,}"
        )
        if corr.stories:
            for s in corr.stories:
                lines.append(f"  [{s.published_at[:10]}] {s.source}: {s.title}")
        else:
            lines.append("  (no news stories found)")
    if not result["correlations"]:
        lines.append("  (no significant moves in this period)")
    return "\n".join(lines)


def _narrate(messages: list[dict[str, str]], last_result: dict[str, Any] | None) -> str:
    data_section = (
        "Current stock data:\n" + _format_result(last_result)
        if last_result is not None
        else "No stock data has been loaded yet."
    )
    system = _NARRATE_SYSTEM.format(data_section=data_section)
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system,
        messages=messages,
    )
    return resp.content[0].text


def _run_correlation(query: dict[str, Any]) -> dict[str, Any] | str:
    ticker = query["ticker"].upper()
    try:
        start = datetime.date.fromisoformat(query["from"])
        end = datetime.date.fromisoformat(query["to"])
    except (ValueError, KeyError) as exc:
        return f"Invalid date in query: {exc}"

    threshold = float(query.get("threshold", 2.0))
    window = int(query.get("window", 1))
    source = str(query.get("source", "finnhub"))

    try:
        df = prices.fetch_history(ticker, start, end)
    except prices.NotFound as exc:
        return str(exc)

    moves = prices.find_moves(df, ticker, threshold_pct=threshold)

    if source == "none":
        corrs = [correlate.Correlation(move=m) for m in moves]
    elif source in _SOURCES:
        fetch_fn, env_var = _SOURCES[source]
        api_key = os.environ.get(env_var, "")
        if not api_key:
            return f"{env_var} is not set in the environment"
        corrs = correlate.correlate(moves, fetch_fn, window_days=window, api_key=api_key)
    else:
        return f"Unknown source: {source!r}"

    return {
        "ticker": ticker,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "correlations": corrs,
    }


def post_message(session_id: str, message: str) -> str:
    session = _get_or_create(session_id)
    session["messages"].append({"role": "user", "content": message})

    query = _extract_query(session["messages"])

    if query is not None:
        result = _run_correlation(query)
        if isinstance(result, str):
            session["messages"].append({"role": "assistant", "content": result})
            return result
        session["last_result"] = result

    reply = _narrate(session["messages"], session["last_result"])
    session["messages"].append({"role": "assistant", "content": reply})
    return reply
