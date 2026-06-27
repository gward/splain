"""Command-line interface for splain."""

import os

from dotenv import load_dotenv

load_dotenv()
from datetime import date, timedelta
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.table import Table

from splain.correlate import correlate
from splain.prices import fetch_history, find_moves

app = typer.Typer(help="Explain stock price moves with contemporary news stories.")
console = Console()


def _default_start() -> str:
    return (date.today() - timedelta(days=90)).isoformat()


def _default_end() -> str:
    return date.today().isoformat()


@app.command()
def main(
    ticker: Annotated[str, typer.Argument(help="Stock ticker symbol, e.g. AAPL")],
    start: Annotated[str, typer.Option("--from", help="Start date YYYY-MM-DD")] = _default_start(),
    end: Annotated[str, typer.Option("--to", help="End date YYYY-MM-DD")] = _default_end(),
    threshold: Annotated[float, typer.Option("--threshold", "-t", help="Min abs % move to report")] = 3.0,
    window: Annotated[int, typer.Option("--window", "-w", help="News search window ±days around move")] = 1,
    api_key: Annotated[Optional[str], typer.Option("--api-key", envvar="NEWSAPI_KEY", help="NewsAPI key")] = None,
) -> None:
    ticker = ticker.upper()
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)

    console.print(f"[bold]Fetching price history for {ticker}[/bold] ({start} → {end})")
    df = fetch_history(ticker, start_date, end_date)
    moves = find_moves(df, ticker, threshold_pct=threshold)

    if not moves:
        console.print(f"[yellow]No moves ≥ {threshold}% found in this period.[/yellow]")
        raise typer.Exit()

    resolved_key = api_key or os.environ.get("NEWSAPI_KEY")
    if resolved_key:
        console.print(f"Found [bold]{len(moves)}[/bold] move(s) ≥ {threshold}%. Fetching news...\n")
        correlations = correlate(moves, window_days=window, api_key=resolved_key)
    else:
        console.print(
            f"Found [bold]{len(moves)}[/bold] move(s) ≥ {threshold}%. "
            "[yellow](Set NEWSAPI_KEY to fetch news.)[/yellow]\n"
        )
        from splain.correlate import Correlation
        correlations = [Correlation(move=m) for m in moves]

    for corr in correlations:
        m = corr.move
        direction = "▲" if m.pct_change > 0 else "▼"
        color = "green" if m.pct_change > 0 else "red"
        console.rule(
            f"[{color}]{direction} {m.pct_change:+.1f}%[/{color}]  "
            f"[bold]{m.ticker}[/bold]  {m.date}  "
            f"(close ${m.close:.2f})"
        )

        if not corr.stories:
            console.print("  [dim]No news stories found.[/dim]\n")
            continue

        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
        table.add_column("Published", style="dim", width=12)
        table.add_column("Source", width=18)
        table.add_column("Headline")

        for story in corr.stories:
            pub = story.published_at[:10]
            table.add_row(pub, story.source, story.title)

        console.print(table)
        console.print()
