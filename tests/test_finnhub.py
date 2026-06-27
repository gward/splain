"""Tests for Finnhub news fetching."""

import datetime

import pytest
import responses

from splain import finnhub, news

FINNHUB_URL = "https://finnhub.io/api/v1/company-news"

FINNHUB_RESPONSE = [
    {
        "headline": "Apple Reports Record Quarter",
        "source": "Reuters",
        "datetime": 1706868000,  # 2024-02-02T10:00:00Z
        "url": "https://example.com/article",
        "summary": "Apple beats estimates.",
    }
]


@responses.activate
def test_fetch_stories_returns_news_story_objects():
    responses.add(responses.GET, FINNHUB_URL, json=FINNHUB_RESPONSE, status=200)

    stories = finnhub.fetch_stories("AAPL", datetime.date(2024, 2, 2), 1, "test-key")

    assert len(stories) == 1
    assert isinstance(stories[0], news.NewsStory)
    assert stories[0].title == "Apple Reports Record Quarter"
    assert stories[0].source == "Reuters"
    assert stories[0].url == "https://example.com/article"


@responses.activate
def test_fetch_stories_returns_empty_list_when_no_articles():
    responses.add(responses.GET, FINNHUB_URL, json=[], status=200)

    stories = finnhub.fetch_stories("AAPL", datetime.date(2024, 2, 2), 1, "test-key")

    assert stories == []


@responses.activate
def test_fetch_stories_raises_on_http_error():
    responses.add(responses.GET, FINNHUB_URL, status=403)

    with pytest.raises(Exception):
        finnhub.fetch_stories("AAPL", datetime.date(2024, 2, 2), 1, "bad-key")
