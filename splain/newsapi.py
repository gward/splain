"""Fetch news stories from NewsAPI (newsapi.org)."""

import datetime

import requests

from splain import news


def fetch_stories(
    query: str,
    around: datetime.date,
    window_days: int,
    api_key: str,
) -> list[news.NewsStory]:
    """Return news stories matching *query* within *window_days* of *around*."""
    from_dt = around - datetime.timedelta(days=window_days)
    to_dt = around + datetime.timedelta(days=window_days)

    resp = requests.get(
        "https://newsapi.org/v2/everything",
        params={
            "q": query,
            "from": from_dt.isoformat(),
            "to": to_dt.isoformat(),
            "sortBy": "relevancy",
            "pageSize": "10",
            "language": "en",
        },
        headers={"X-Api-Key": api_key},
        timeout=10,
    )
    if resp.status_code == 426:
        # Free tier only covers the past ~1 month
        return []
    resp.raise_for_status()

    return [
        news.NewsStory(
            title=art["title"],
            source=art["source"]["name"],
            published_at=art["publishedAt"],
            url=art["url"],
            description=art.get("description"),
        )
        for art in resp.json().get("articles", [])
    ]
