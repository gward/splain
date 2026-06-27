"""Tests for news fetching (uses vcr cassettes to avoid live HTTP)."""

import datetime
from unittest import mock

import pytest

from splain import news


MOCK_RESPONSE = {
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


def test_fetch_stories_returns_news_story_objects():
    mock_resp = mock.MagicMock()
    mock_resp.json.return_value = MOCK_RESPONSE
    mock_resp.raise_for_status.return_value = None

    with mock.patch("splain.news.requests.get", return_value=mock_resp):
        stories = news.fetch_stories("AAPL", datetime.date(2024, 2, 2), api_key="test-key")

    assert len(stories) == 1
    assert isinstance(stories[0], news.NewsStory)
    assert stories[0].title == "Apple Reports Record Quarter"
    assert stories[0].source == "Reuters"


def test_fetch_stories_raises_without_api_key(monkeypatch):
    monkeypatch.delenv("NEWSAPI_KEY", raising=False)
    with pytest.raises(EnvironmentError, match="NEWSAPI_KEY"):
        news.fetch_stories("AAPL", datetime.date(2024, 2, 2))
