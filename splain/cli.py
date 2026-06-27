"""Command-line interface for splain."""

import datetime
import os

import click
import dotenv

from splain import correlate, finnhub, news, newsapi, prices

dotenv.load_dotenv()

SOURCES = {
    "newsapi": (newsapi.fetch_stories, "NEWSAPI_KEY"),
    "finnhub": (finnhub.fetch_stories, "FINNHUB_KEY"),
}


def _default_start() -> str:
    return (datetime.date.today() - datetime.timedelta(days=90)).isoformat()


def _default_end() -> str:
    return datetime.date.today().isoformat()


@click.command(context_settings={"show_default": True})
@click.argument("ticker", required=False)
@click.option(
    "--from",
    "start",
    default=_default_start,
    metavar="START",
    show_default="today - 90 days",
    help="Start date (YYYY-MM-DD)",
)
@click.option(
    "--to",
    "end",
    default=_default_end,
    metavar="END",
    show_default="today",
    help="End date YYYY-MM-DD",
)
@click.option(
    "--threshold",
    "-t",
    default=2.0,
    metavar="T",
    help="Minimum absolute move to report (percentage)",
)
@click.option(
    "--window",
    "-w",
    metavar="W",
    default=1,
    help="News search window +/-days around move",
)
@click.option(
    "--source",
    "-s",
    type=click.Choice(["newsapi", "finnhub", "none"]),
    default="finnhub",
    help="News source (requires corresponding API key in env)",
)
@click.option(
    "--api",
    "use_api",
    is_flag=True,
    default=False,
    help="Start REST API server instead of running a one-shot analysis",
)
@click.option(
    "--port",
    default=5000,
    help="Port for the API server",
)
def app(
    ticker: str | None,
    start: str,
    end: str,
    threshold: float,
    window: int,
    source: str,
    use_api: bool,
    port: int,
) -> None:
    """Explain stock price moves with contemporary news stories."""
    if use_api:
        from splain import server

        print(f"Starting API server on http://127.0.0.1:{port}")
        server.app.run(host="127.0.0.1", port=port)
        return

    if not ticker:
        raise click.UsageError("TICKER is required when not using --api")

    ticker = ticker.upper()
    start_date = datetime.date.fromisoformat(start)
    end_date = datetime.date.fromisoformat(end)

    fetch_fn: news.FetchFunction | None
    if source != "none":
        fetch_fn, env_var = SOURCES[source]
        api_key = os.environ.get(env_var)
        if not api_key:
            raise click.ClickException(f"{env_var} not set in environment")
    else:
        fetch_fn, api_key = None, ""

    print(f"Fetching price history for {ticker} ({start} to {end})")
    try:
        df = prices.fetch_history(ticker, start_date, end_date)
    except prices.NotFound as e:
        raise click.ClickException(str(e)) from e
    moves = prices.find_moves(df, ticker, threshold_pct=threshold)

    if not moves:
        print(f"No moves >= {threshold}% found in this period.")
        return

    if fetch_fn:
        print(f"Found {len(moves)} move(s) >= {threshold}%. Fetching news...\n")
        correlations = correlate.correlate(moves, fetch_fn, window_days=window, api_key=api_key)
    else:
        print(f"Found {len(moves)} move(s) >= {threshold}%.\n")
        correlations = [correlate.Correlation(move=m) for m in moves]

    for corr in correlations:
        m = corr.move
        direction = "+" if m.pct_change > 0 else ""
        header = f"{direction}{m.pct_change:.1f}%  {m.ticker}  {m.date}  close ${m.close:.2f}"
        print(header)
        print("-" * len(header))

        if not corr.stories:
            print("  No news stories found.\n")
            continue

        for story in corr.stories:
            pub = story.published_at[:10]
            print(f"  {pub}  {story.source}")
            print(f"  {story.title}")
            print(f"  {story.url}\n")
