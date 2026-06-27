"""Pair price moves with nearby news stories."""

from dataclasses import dataclass, field

from splain.news import NewsStory, fetch_stories
from splain.prices import PriceMove


@dataclass
class Correlation:
    move: PriceMove
    stories: list[NewsStory] = field(default_factory=list)


def correlate(
    moves: list[PriceMove],
    window_days: int = 1,
    api_key: str | None = None,
) -> list[Correlation]:
    """For each price move, fetch news stories from around that date."""
    results = []
    for move in moves:
        stories = fetch_stories(
            query=move.ticker,
            around=move.date,
            window_days=window_days,
            api_key=api_key,
        )
        results.append(Correlation(move=move, stories=stories))
    return results
