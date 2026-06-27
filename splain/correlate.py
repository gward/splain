"""Pair price moves with nearby news stories."""

import dataclasses

from splain import news, prices


@dataclasses.dataclass
class Correlation:
    move: prices.PriceMove
    stories: list[news.NewsStory] = dataclasses.field(default_factory=list)


def correlate(
    moves: list[prices.PriceMove],
    fetch_fn,
    window_days: int = 1,
    api_key: str | None = None,
) -> list[Correlation]:
    """For each price move, fetch news stories from around that date."""
    results = []
    for move in moves:
        stories = fetch_fn(
            query=move.ticker,
            around=move.date,
            window_days=window_days,
            api_key=api_key,
        )
        results.append(Correlation(move=move, stories=stories))
    return results
