"""Tests for price fetching and move detection."""

from datetime import date

import pandas as pd
import pytest

from splain.prices import PriceMove, find_moves


def _make_df(closes: list[float]) -> pd.DataFrame:
    dates = [date(2024, 1, d + 1) for d in range(len(closes))]
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Volume": [1_000_000] * len(closes),
        },
        index=dates,
    )


def test_find_moves_detects_large_drop():
    df = _make_df([100.0, 100.0, 85.0, 85.0])  # -15% on day 3
    moves = find_moves(df, "TEST", threshold_pct=5.0)
    assert len(moves) == 1
    assert moves[0].pct_change == pytest.approx(-15.0)


def test_find_moves_detects_large_gain():
    df = _make_df([100.0, 110.0])  # +10%
    moves = find_moves(df, "TEST", threshold_pct=5.0)
    assert len(moves) == 1
    assert moves[0].pct_change == pytest.approx(10.0)


def test_find_moves_ignores_small_change():
    df = _make_df([100.0, 101.0, 102.0])
    moves = find_moves(df, "TEST", threshold_pct=5.0)
    assert moves == []


def test_find_moves_returns_price_move_dataclass():
    df = _make_df([100.0, 90.0])
    moves = find_moves(df, "ACME", threshold_pct=5.0)
    assert isinstance(moves[0], PriceMove)
    assert moves[0].ticker == "ACME"
