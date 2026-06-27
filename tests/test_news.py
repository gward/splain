"""Tests for news fetching."""

import datetime

import pytest
import responses

from splain import news


NEWSAPI_URL = "https://newsapi.org/v2/everything"

NEWSAPI_RESPONSE = {
    "status": "ok",
    "totalResults": 1,
    "articles": [
        {
            "title": "Apple Reports Record Quarter",
            "source": {"name": "Reuters"},
            "publishedAt": "2024-02-02T10:00:00Z",
            "url": "https://example.com/article",
            "description": "Apple beats estimates.",
        }
    ],
}


@responses.activate
def test_fetch_stories_returns_news_story_objects():
    responses.add(responses.GET, NEWSAPI_URL, json=NEWSAPI_RESPONSE, status=200)

    stories = news.fetch_stories("AAPL", datetime.date(2024, 2, 2), api_key="test-key")

    assert len(stories) == 1
    assert isinstance(stories[0], news.NewsStory)
    assert stories[0].title == "Apple Reports Record Quarter"
    assert stories[0].source == "Reuters"


@responses.activate
def test_fetch_stories_returns_empty_on_426():
    responses.add(responses.GET, NEWSAPI_URL, status=426)

    stories = news.fetch_stories("AAPL", datetime.date(2020, 1, 1), api_key="test-key")

    assert stories == []


def test_fetch_stories_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("NEWSAPI_KEY", raising=False)
    with pytest.raises(EnvironmentError, match="NEWSAPI_KEY"):
        news.fetch_stories("AAPL", datetime.date(2024, 2, 2))
