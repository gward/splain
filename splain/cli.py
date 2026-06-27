"""Command-line interface for splain."""

import datetime
import os

import click
import dotenv

from splain import correlate, prices

dotenv.load_dotenv()


def _default_start() -> str:
    return (datetime.date.today() - datetime.timedelta(days=90)).isoformat()


def _default_end() -> str:
    return datetime.date.today().isoformat()


@click.command()
@click.argument("ticker")
@click.option("--from", "start", default=_default_start, help="Start date YYYY-MM-DD")
@click.option("--to", "end", default=_default_end, help="End date YYYY-MM-DD")
@click.option("--threshold", "-t", default=3.0, help="Min abs % move to report")
@click.option("--window", "-w", default=1, help="News search window +/-days around move")
@click.option("--api-key", envvar="NEWSAPI_KEY", default=None, help="NewsAPI key")
def main(ticker, start, end, threshold, window, api_key):
    """Explain stock price moves with contemporary news stories."""
    ticker = ticker.upper()
    start_date = datetime.date.fromisoformat(start)
    end_date = datetime.date.fromisoformat(end)

    print(f"Fetching price history for {ticker} ({start} to {end})")
    df = prices.fetch_history(ticker, start_date, end_date)
    moves = prices.find_moves(df, ticker, threshold_pct=threshold)

    if not moves:
        print(f"No moves >= {threshold}% found in this period.")
        return

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


app = main
