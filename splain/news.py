"""Fetch news stories around a given date."""

import dataclasses
import datetime
import os

import requests


@dataclasses.dataclass
class NewsStory:
    title: str
    source: str
    published_at: str
    url: str
    description: str | None = None


def fetch_stories(
    query: str,
    around: datetime.date,
    window_days: int = 1,
    api_key: str | None = None,
) -> list[NewsStory]:
    """Return news stories matching *query* within *window_days* of *around*.

    Uses NewsAPI (newsapi.org). Set NEWSAPI_KEY env var or pass api_key.
    """
    if api_key is None:
        api_key = os.environ.get("NEWSAPI_KEY")
    if not api_key:
        raise EnvironmentError("NEWSAPI_KEY not set -- get a free key at newsapi.org")

    from_dt = around - datetime.timedelta(days=window_days)
    to_dt = around + datetime.timedelta(days=window_days)

    resp = requests.get(
        "https://newsapi.org/v2/everything",
        params={
            "q": query,
            "from": from_dt.isoformat(),
            "to": to_dt.isoformat(),
            "sortBy": "relevancy",
            "pageSize": 10,
            "language": "en",
        },
        headers={"X-Api-Key": api_key},
        timeout=10,
    )
    if resp.status_code == 426:
        # Free tier only covers the past ~1 month
        return []
    resp.raise_for_status()
    data = resp.json()

    return [
        NewsStory(
            title=art["title"],
            source=art["source"]["name"],
            published_at=art["publishedAt"],
            url=art["url"],
            description=art.get("description"),
        )
        for art in data.get("articles", [])
    ]
