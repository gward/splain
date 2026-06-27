"""Fetch news stories from Finnhub (finnhub.io)."""

import datetime

import requests

from splain import news


def fetch_stories(
    query: str,
    around: datetime.date,
    window_days: int,
    api_key: str,
) -> list[news.NewsStory]:
    """Return news stories for *query* (ticker symbol) within *window_days* of *around*."""
    from_dt = around - datetime.timedelta(days=window_days)
    to_dt = around + datetime.timedelta(days=window_days)

    resp = requests.get(
        "https://finnhub.io/api/v1/company-news",
        params={
            "symbol": query,
            "from": from_dt.isoformat(),
            "to": to_dt.isoformat(),
        },
        headers={"X-Finnhub-Token": api_key},
        timeout=10,
    )
    resp.raise_for_status()

    return [
        news.NewsStory(
            title=art["headline"],
            source=art["source"],
            published_at=datetime.datetime.fromtimestamp(art["datetime"], tz=datetime.timezone.utc).isoformat(),
            url=art["url"],
            description=art.get("summary"),
        )
        for art in resp.json()
    ]
