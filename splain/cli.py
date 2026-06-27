"""Command-line interface for splain."""

import datetime
import os
import typing

import dotenv
import typer

from splain import correlate, prices

dotenv.load_dotenv()

app = typer.Typer(
    help="Explain stock price moves with contemporary news stories.",
    rich_markup_mode=None,
)


def _default_start() -> str:
    return (datetime.date.today() - datetime.timedelta(days=90)).isoformat()


def _default_end() -> str:
    return datetime.date.today().isoformat()


@app.command()
def main(
    ticker: typing.Annotated[str, typer.Argument(help="Stock ticker symbol, e.g. AAPL")],
    start: typing.Annotated[str, typer.Option("--from", help="Start date YYYY-MM-DD")] = _default_start(),
    end: typing.Annotated[str, typer.Option("--to", help="End date YYYY-MM-DD")] = _default_end(),
    threshold: typing.Annotated[float, typer.Option("--threshold", "-t", help="Min abs % move to report")] = 3.0,
    window: typing.Annotated[int, typer.Option("--window", "-w", help="News search window +/-days around move")] = 1,
    api_key: typing.Annotated[
        typing.Optional[str], typer.Option("--api-key", envvar="NEWSAPI_KEY", help="NewsAPI key")
    ] = None,
) -> None:
    ticker = ticker.upper()
    start_date = datetime.date.fromisoformat(start)
    end_date = datetime.date.fromisoformat(end)

    print(f"Fetching price history for {ticker} ({start} to {end})")
    df = prices.fetch_history(ticker, start_date, end_date)
    moves = prices.find_moves(df, ticker, threshold_pct=threshold)

    if not moves:
        print(f"No moves >= {threshold}% found in this period.")
        raise typer.Exit()

    resolved_key = api_key or os.environ.get("NEWSAPI_KEY")
    if resolved_key:
        print(f"Found {len(moves)} move(s) >= {threshold}%. Fetching news...\n")
        correlations = correlate.correlate(moves, window_days=window, api_key=resolved_key)
    else:
        print(f"Found {len(moves)} move(s) >= {threshold}%. Set NEWSAPI_KEY to fetch news.\n")
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
            print(f"  {story.title}\n")
