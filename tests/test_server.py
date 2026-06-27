"""Tests for the Flask API server."""

import datetime

import pytest

from splain import correlate, news, prices
from splain.server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _fake_move() -> prices.PriceMove:
    return prices.PriceMove(
        ticker="TSLA",
        date=datetime.date(2024, 5, 12),
        open=321.50,
        close=298.10,
        pct_change=-7.3,
        volume=123456789,
    )


def _fake_story() -> news.NewsStory:
    return news.NewsStory(
        title="Tesla misses estimates",
        source="Reuters",
        published_at="2024-05-12T14:30:00+00:00",
        url="https://example.com/article",
        description="Details here.",
    )


def test_correlations_returns_json_with_correct_shape(client, monkeypatch):
    monkeypatch.setenv("FINNHUB_KEY", "test-key")
    monkeypatch.setattr(prices, "fetch_history", lambda *a, **kw: object())
    monkeypatch.setattr(prices, "find_moves", lambda *a, **kw: [_fake_move()])
    monkeypatch.setattr(
        correlate,
        "correlate",
        lambda moves, fn, window_days, api_key: [correlate.Correlation(move=moves[0], stories=[_fake_story()])],
    )

    resp = client.get("/correlations/TSLA")
    assert resp.status_code == 200

    data = resp.get_json()
    assert data["ticker"] == "TSLA"
    assert len(data["moves"]) == 1
    move = data["moves"][0]
    assert move["date"] == "2024-05-12"
    assert move["pct_change"] == pytest.approx(-7.3)
    assert len(move["stories"]) == 1
    assert move["stories"][0]["title"] == "Tesla misses estimates"


def test_correlations_uppercases_ticker(client, monkeypatch):
    monkeypatch.setenv("FINNHUB_KEY", "test-key")
    monkeypatch.setattr(prices, "fetch_history", lambda *a, **kw: object())
    monkeypatch.setattr(prices, "find_moves", lambda *a, **kw: [])
    monkeypatch.setattr(correlate, "correlate", lambda *a, **kw: [])

    resp = client.get("/correlations/tsla")
    data = resp.get_json()
    assert data["ticker"] == "TSLA"


def test_correlations_bad_date_returns_400(client, monkeypatch):
    monkeypatch.setenv("FINNHUB_KEY", "test-key")
    resp = client.get("/correlations/TSLA?from=not-a-date")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_correlations_unknown_source_returns_400(client):
    resp = client.get("/correlations/TSLA?source=unknown")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_correlations_missing_api_key_returns_503(client, monkeypatch):
    monkeypatch.delenv("FINNHUB_KEY", raising=False)
    resp = client.get("/correlations/TSLA?source=finnhub")
    assert resp.status_code == 503
    assert "error" in resp.get_json()


def test_correlations_ticker_not_found_returns_404(client, monkeypatch):
    monkeypatch.setenv("FINNHUB_KEY", "test-key")

    def raise_not_found(*a, **kw):
        raise prices.NotFound("no data for INVALID")

    monkeypatch.setattr(prices, "fetch_history", raise_not_found)

    resp = client.get("/correlations/INVALID")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_correlations_source_none_returns_moves_without_stories(client, monkeypatch):
    monkeypatch.setattr(prices, "fetch_history", lambda *a, **kw: object())
    monkeypatch.setattr(prices, "find_moves", lambda *a, **kw: [_fake_move()])

    resp = client.get("/correlations/TSLA?source=none")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["moves"][0]["stories"] == []
