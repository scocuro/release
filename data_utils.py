"""
Price fetching.

Unlike the old fetch_last_close(ticker) -> float, this returns
Quote(price, obs_date, error).

Why: running this in the Korean morning means KOSPI200 gives yesterday's
close, S&P500 gives yesterday's US session, and Nikkei may be two days old
on a holiday. The old code lumped everything under "today", so a stale
price was invisible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class Quote:
    ticker: str
    price: float | None = None
    obs_date: date | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.price is not None and self.obs_date is not None

    def stale_days(self, today: date) -> int | None:
        if not self.obs_date:
            return None
        return (today - self.obs_date).days


def fetch_quote(ticker: str, lookback_days: int = 10) -> Quote:
    """
    Return the last valid close AND the actual date of that close.
    Never raises - one bad ticker must not kill the whole report.
    """
    try:
        import yfinance as yf
    except ImportError:
        return Quote(ticker, error="yfinance not installed")

    try:
        end = date.today() + timedelta(days=1)
        start = end - timedelta(days=lookback_days)
        df = yf.download(
            ticker, start=start, end=end,
            progress=False, auto_adjust=False, threads=False,
        )
        if df is None or df.empty:
            return Quote(ticker, error="no data returned")

        close = df["Close"]
        if hasattr(close, "columns"):          # guard against MultiIndex
            close = close.iloc[:, 0]
        close = close.dropna()
        if close.empty:
            return Quote(ticker, error="no valid close")

        return Quote(ticker,
                     price=float(close.iloc[-1]),
                     obs_date=close.index[-1].date())
    except Exception as e:                      # noqa: BLE001
        return Quote(ticker, error=f"{type(e).__name__}: {e}")


def fetch_history(ticker: str, start: date, end: date):
    """For backfill. Returns a list of (date, close)."""
    try:
        import yfinance as yf
    except ImportError:
        raise RuntimeError("yfinance required: pip install yfinance")

    df = yf.download(ticker, start=start, end=end + timedelta(days=1),
                     progress=False, auto_adjust=False, threads=False)
    if df is None or df.empty:
        return []
    close = df["Close"]
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    close = close.dropna()
    return [(idx.date(), float(v)) for idx, v in close.items()]


def sanity_flag(level_pct: float, hi: float, lo: float) -> str | None:
    """
    Warn when close/strike falls outside a sane range.
    Catches stock splits where the adjusted price no longer matches
    the strike on the term sheet, instead of failing silently.
    """
    if level_pct is None:
        return None
    if level_pct > hi:
        return (f"종가가 기준가의 {level_pct*100:.1f}% — 액면분할/수정주가 불일치 의심. "
                f"발행사 공시 기준가 대조 요망")
    if level_pct < lo:
        return (f"종가가 기준가의 {level_pct*100:.1f}% — 병합/기준가 오입력 가능성. "
                f"단순 급락일 수 있으니 1회 육안 확인 권장")
    return None
