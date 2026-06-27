"""Flask HTTP server exposing stock correlation data as JSON."""

import datetime
import os

import flask

from splain import correlate, finnhub, news, newsapi, prices

app = flask.Flask(__name__)

SOURCES: dict[str, tuple[news.FetchFunction, str]] = {
    "newsapi": (newsapi.fetch_stories, "NEWSAPI_KEY"),
    "finnhub": (finnhub.fetch_stories, "FINNHUB_KEY"),
}


def _default_start() -> datetime.date:
    return datetime.date.today() - datetime.timedelta(days=90)


def _default_end() -> datetime.date:
    return datetime.date.today()


@app.route("/correlations/<ticker>")
def get_correlations(ticker: str) -> flask.Response:
    ticker = ticker.upper()

    try:
        start = datetime.date.fromisoformat(flask.request.args.get("from", _default_start().isoformat()))
        end = datetime.date.fromisoformat(flask.request.args.get("to", _default_end().isoformat()))
    except ValueError as exc:
        return flask.jsonify({"error": str(exc)}), 400  # type: ignore[return-value]

    try:
        threshold = float(flask.request.args.get("threshold", "2.0"))
        window = int(flask.request.args.get("window", "1"))
    except ValueError as exc:
        return flask.jsonify({"error": str(exc)}), 400  # type: ignore[return-value]

    source = flask.request.args.get("source", "finnhub")

    fetch_fn: news.FetchFunction | None
    api_key: str
    if source == "none":
        fetch_fn, api_key = None, ""
    elif source in SOURCES:
        fetch_fn, env_var = SOURCES[source]
        api_key = os.environ.get(env_var, "")
        if not api_key:
            return flask.jsonify({"error": f"{env_var} not set in environment"}), 503  # type: ignore[return-value]
    else:
        return flask.jsonify({"error": f"unknown source: {source!r}"}), 400  # type: ignore[return-value]

    try:
        df = prices.fetch_history(ticker, start, end)
    except prices.NotFound as exc:
        return flask.jsonify({"error": str(exc)}), 404  # type: ignore[return-value]

    moves = prices.find_moves(df, ticker, threshold_pct=threshold)

    if fetch_fn is not None:
        correlations = correlate.correlate(moves, fetch_fn, window_days=window, api_key=api_key)
    else:
        correlations = [correlate.Correlation(move=m) for m in moves]

    return flask.jsonify(
        {
            "ticker": ticker,
            "from": start.isoformat(),
            "to": end.isoformat(),
            "moves": [
                {
                    "date": str(corr.move.date),
                    "open": corr.move.open,
                    "close": corr.move.close,
                    "pct_change": corr.move.pct_change,
                    "volume": corr.move.volume,
                    "stories": [
                        {
                            "title": s.title,
                            "source": s.source,
                            "published_at": s.published_at,
                            "url": s.url,
                            "description": s.description,
                        }
                        for s in corr.stories
                    ],
                }
                for corr in correlations
            ],
        }
    )
