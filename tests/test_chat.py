"""Tests for splain.chat helpers and post_message pipeline."""

import datetime
import json
from unittest.mock import MagicMock, patch

import pytest
from anthropic.types import TextBlock

from splain import chat, correlate, news, prices
from splain.server import app as _flask_app


@pytest.fixture(autouse=True)
def reset_sessions():
    chat._sessions.clear()
    yield
    chat._sessions.clear()


def _fake_move() -> prices.PriceMove:
    return prices.PriceMove(
        ticker="TSLA",
        date=datetime.date(2026, 6, 20),
        open=200.0,
        close=186.0,
        pct_change=-7.0,
        volume=50_000_000,
    )


def _fake_story() -> news.NewsStory:
    return news.NewsStory(
        title="Tesla recall announced",
        source="Reuters",
        published_at="2026-06-20T10:00:00+00:00",
        url="https://example.com/article",
        description="Details about the recall.",
    )


def _anthropic_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.content = [TextBlock(type="text", text=text)]
    return resp


# --- _format_result ---


def test_format_result_includes_ticker_and_move():
    result = {
        "ticker": "TSLA",
        "from": "2026-06-01",
        "to": "2026-06-27",
        "correlations": [correlate.Correlation(move=_fake_move(), stories=[_fake_story()])],
    }
    text = chat._format_result(result)
    assert "TSLA" in text
    assert "-7.0%" in text
    assert "Tesla recall announced" in text


def test_format_result_no_stories_note():
    result = {
        "ticker": "AAPL",
        "from": "2026-06-01",
        "to": "2026-06-27",
        "correlations": [
            correlate.Correlation(
                move=prices.PriceMove(
                    ticker="AAPL",
                    date=datetime.date(2026, 6, 15),
                    open=190.0,
                    close=200.0,
                    pct_change=5.2,
                    volume=30_000_000,
                ),
                stories=[],
            )
        ],
    }
    text = chat._format_result(result)
    assert "no news stories" in text


def test_format_result_no_moves_note():
    result = {
        "ticker": "MSFT",
        "from": "2026-06-01",
        "to": "2026-06-27",
        "correlations": [],
    }
    text = chat._format_result(result)
    assert "no significant moves" in text


# --- clear_session ---


def test_clear_session_removes_existing():
    chat._sessions["s1"] = {"messages": [], "last_result": None}
    chat.clear_session("s1")
    assert "s1" not in chat._sessions


def test_clear_session_nonexistent_is_ok():
    chat.clear_session("never-existed")  # must not raise


# --- post_message: new session auto-created ---


def test_post_message_creates_session_and_returns_reply(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    extract_resp = _anthropic_response("null")
    narrate_resp = _anthropic_response("No data yet. What stock?")

    with patch("splain.chat.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = [extract_resp, narrate_resp]
        reply = chat.post_message("new-session", "Hello!")

    assert reply == "No data yet. What stock?"
    assert "new-session" in chat._sessions
    msgs = chat._sessions["new-session"]["messages"]
    assert msgs[0] == {"role": "user", "content": "Hello!"}
    assert msgs[1] == {"role": "assistant", "content": "No data yet. What stock?"}


# --- post_message: extraction returns query, correlation runs ---


def test_post_message_runs_correlation_on_query(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("FINNHUB_KEY", "fh-key")

    query_json = json.dumps(
        {
            "ticker": "TSLA",
            "from": "2026-06-01",
            "to": "2026-06-27",
            "threshold": 2.0,
            "window": 1,
            "source": "finnhub",
        }
    )
    extract_resp = _anthropic_response(query_json)
    narrate_resp = _anthropic_response("Tesla dropped 7% due to a recall.")

    with patch("splain.chat.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = [extract_resp, narrate_resp]
        monkeypatch.setattr(prices, "fetch_history", lambda *a, **kw: object())
        monkeypatch.setattr(prices, "find_moves", lambda *a, **kw: [_fake_move()])
        monkeypatch.setattr(
            correlate,
            "correlate",
            lambda *a, **kw: [correlate.Correlation(move=_fake_move(), stories=[_fake_story()])],
        )
        reply = chat.post_message("s2", "Why did TSLA drop?")

    assert reply == "Tesla dropped 7% due to a recall."
    assert chat._sessions["s2"]["last_result"]["ticker"] == "TSLA"


# --- post_message: null extraction uses cached last_result, no refetch ---


def test_post_message_followup_uses_cache(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    cached = {
        "ticker": "TSLA",
        "from": "2026-06-01",
        "to": "2026-06-27",
        "correlations": [correlate.Correlation(move=_fake_move(), stories=[])],
    }
    chat._sessions["s3"] = {
        "messages": [
            {"role": "user", "content": "Why did TSLA drop?"},
            {"role": "assistant", "content": "TSLA dropped 7% on June 20."},
        ],
        "last_result": cached,
    }

    extract_resp = _anthropic_response("null")
    narrate_resp = _anthropic_response("Supply chain issues drove the drop.")

    fetched = []
    with patch("splain.chat.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = [extract_resp, narrate_resp]
        monkeypatch.setattr(prices, "fetch_history", lambda *a, **kw: fetched.append(1))
        reply = chat.post_message("s3", "Can you elaborate?")

    assert reply == "Supply chain issues drove the drop."
    assert fetched == []  # prices not re-fetched
    assert chat._sessions["s3"]["last_result"] is cached  # unchanged


# --- post_message: malformed extraction JSON falls back to last_result ---


def test_post_message_malformed_extraction_uses_cache(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    cached = {
        "ticker": "TSLA",
        "from": "2026-06-01",
        "to": "2026-06-27",
        "correlations": [],
    }
    chat._sessions["s4"] = {"messages": [], "last_result": cached}

    extract_resp = _anthropic_response("not valid json")
    narrate_resp = _anthropic_response("No significant moves in that period.")

    with patch("splain.chat.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = [extract_resp, narrate_resp]
        reply = chat.post_message("s4", "Anything interesting?")

    assert reply == "No significant moves in that period."
    assert chat._sessions["s4"]["last_result"] is cached  # unchanged


# --- post_message: stock data error surfaced as reply ---


def test_post_message_ticker_not_found_returns_error_reply(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("FINNHUB_KEY", "fh-key")

    query_json = json.dumps(
        {
            "ticker": "INVALID",
            "from": "2026-06-01",
            "to": "2026-06-27",
            "threshold": 2.0,
            "window": 1,
            "source": "finnhub",
        }
    )
    extract_resp = _anthropic_response(query_json)

    def raise_not_found(*a, **kw):
        raise prices.NotFound("No price data returned for 'INVALID'")

    with patch("splain.chat.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = [extract_resp]
        monkeypatch.setattr(prices, "fetch_history", raise_not_found)
        reply = chat.post_message("s5", "Tell me about INVALID")

    assert "INVALID" in reply or "price data" in reply.lower()
    # narrate not called (only 1 Claude call consumed)
    assert MockClient.return_value.messages.create.call_count == 1


# --- route integration tests ---


@pytest.fixture
def client():
    _flask_app.config["TESTING"] = True
    with _flask_app.test_client() as c:
        yield c


def test_route_missing_api_key_returns_503(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resp = client.post("/chat/s1", json={"message": "hello"})
    assert resp.status_code == 503
    assert "error" in resp.get_json()


def test_route_missing_message_field_returns_400(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    resp = client.post("/chat/s1", json={"text": "oops"})
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_route_non_json_body_returns_400(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    resp = client.post("/chat/s1", data="not json", content_type="text/plain")
    assert resp.status_code == 400


def test_route_post_returns_reply(client, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    extract_resp = _anthropic_response("null")
    narrate_resp = _anthropic_response("Welcome! What stock?")

    with patch("splain.chat.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.side_effect = [extract_resp, narrate_resp]
        resp = client.post("/chat/route-test", json={"message": "Hi"})

    assert resp.status_code == 200
    assert resp.get_json()["reply"] == "Welcome! What stock?"


def test_route_delete_clears_session(client):
    chat._sessions["del-me"] = {"messages": [], "last_result": None}
    resp = client.delete("/chat/del-me")
    assert resp.status_code == 200
    assert "del-me" not in chat._sessions


def test_route_delete_nonexistent_ok(client):
    resp = client.delete("/chat/ghost")
    assert resp.status_code == 200
