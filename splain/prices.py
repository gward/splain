"""Fetch and analyse historical stock price data."""

import dataclasses
import datetime

import pandas as pd
import yfinance as yf


@dataclasses.dataclass
class PriceMove:
    ticker: str
    date: datetime.date
    open: float
    close: float
    pct_change: float
    volume: int


def fetch_history(ticker: str, start: datetime.date, end: datetime.date) -> pd.DataFrame:
    """Return OHLCV dataframe for *ticker* over [start, end]."""
    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"No price data returned for {ticker!r}")
    # yfinance >=0.2 returns MultiIndex columns like ("Close", "TSLA") -- flatten them
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.index = pd.to_datetime(df.index).date
    return df


def find_moves(
    df: pd.DataFrame,
    ticker: str,
    threshold_pct: float = 3.0,
) -> list[PriceMove]:
    """Return days where |close-to-close pct change| >= threshold_pct."""
    df = df.copy()
    df["pct_change"] = df["Close"].pct_change() * 100
    significant = df[df["pct_change"].abs() >= threshold_pct]
    return [
        PriceMove(
            ticker=ticker,
            date=idx,
            open=float(row["Open"]),
            close=float(row["Close"]),
            pct_change=float(row["pct_change"]),
            volume=int(row["Volume"]),
        )
        for idx, row in significant.iterrows()
    ]
