"""US stock (美股) unified market API.

Aggregates all US stock data endpoints across vendors.
8-layer architecture with 18+ endpoints.

Layers:
    1. 行情 — Real-time/delayed quotes, K-line
    2. K线 — Multi-period K-line (daily/weekly/monthly/minute)
    3. 技术指标 — MA/MACD/RSI/KDJ/Bollinger
    4. 基本面 — Financials, key statistics (Yahoo 23 modules), SEC XBRL
    5. 资金面 — Daily fund flow (main force vs retail)
    6. 期权 — Options chain with Greeks
    7. SEC Filing — 10-K/10-Q/8-K filings, XBRL financial data
    8. 工具 — Stock search, market list, ticker-CIK mapping
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from mystrategy.data.vendor import (
    eastmoney,
    tencent,
    sina,
    yahoo,
    sec_edgar,
)
from mystrategy.data.cache import get_cache

_cache = get_cache()


# ═══════════════════════════════════════════════════════════════
# Layer 1: 行情层 (Market Data)
# ═══════════════════════════════════════════════════════════════

def realtime(codes: list[str]) -> dict[str, dict]:
    """Get real-time/delayed quotes for US stocks.

    Uses Sina finance (free, no key needed).
    """
    return sina.us_realtime_quotes(codes)


def quote(symbol: str) -> dict:
    """Get single stock quote."""
    result = realtime([symbol])
    return result.get(symbol.upper(), {})


# ═══════════════════════════════════════════════════════════════
# Layer 2: K线层 (K-line)
# ═══════════════════════════════════════════════════════════════

def kline(symbol: str, interval: str = "1d", years: int = 5) -> pd.DataFrame:
    """Get historical K-line from Yahoo Finance.

    Args:
        symbol: ticker (e.g., 'AAPL')
        interval: '1d', '1wk', '1mo', '1m', '5m', '15m', '30m', '60m'
        years: years of history (when interval is daily)
    """
    key = f"kline_us_{symbol}_{interval}_{years}"
    cached = _cache.get_df(key)
    if cached is not None:
        return cached

    df = yahoo.daily_kline(symbol, years=years) if interval == "1d" else \
         yahoo.kline(symbol, interval=interval)

    if not df.empty:
        _cache.set_df(key, df)
    return df


def daily_kline(symbol: str, years: int = 5) -> pd.DataFrame:
    """Get daily K-line."""
    return kline(symbol, interval="1d", years=years)


# ═══════════════════════════════════════════════════════════════
# Layer 3: 技术指标层 (Technical Indicators)
# ═══════════════════════════════════════════════════════════════

def compute_indicators(symbol: str, years: int = 2) -> dict:
    """Compute technical indicators (MA, MACD, RSI, KDJ, Bollinger).

    Returns dict with DataFrames for each indicator.
    """
    df = daily_kline(symbol, years=years)
    if df.empty or len(df) < 60:
        return {}

    close = df["close"].values
    high = df["high"].values
    low = df["low"].values

    # MA
    ma5 = _sma(close, 5)
    ma10 = _sma(close, 10)
    ma20 = _sma(close, 20)
    ma60 = _sma(close, 60)

    # MACD
    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    dif = ema12 - ema26
    dea = _ema(dif, 9)
    macd_bar = 2 * (dif - dea)

    # RSI
    rsi6 = _rsi(close, 6)
    rsi12 = _rsi(close, 12)
    rsi24 = _rsi(close, 24)

    # KDJ
    k, d, j = _kdj(high, low, close, n=9)

    # Bollinger Bands
    bb_mid = _sma(close, 20)
    bb_std = _rolling_std(close, 20)
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std

    result = {
        "date": df["date"].values,
        "ma": {"ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60},
        "macd": {"dif": dif, "dea": dea, "bar": macd_bar},
        "rsi": {"rsi6": rsi6, "rsi12": rsi12, "rsi24": rsi24},
        "kdj": {"k": k, "d": d, "j": j},
        "bollinger": {"upper": bb_upper, "mid": bb_mid, "lower": bb_lower},
    }
    return result


# ═══════════════════════════════════════════════════════════════
# Layer 4: 基本面层 (Fundamentals)
# ═══════════════════════════════════════════════════════════════

def key_statistics(symbol: str) -> dict:
    """Get key statistics: PE, PB, ROE, market cap, revenue growth, etc."""
    return yahoo.key_statistics(symbol)


def financial_modules(symbol: str, modules: list[str] | None = None) -> dict:
    """Get Yahoo Finance financial data modules (up to 23)."""
    return yahoo.get_modules(symbol, modules)


def sec_financials(cik: str) -> dict:
    """Get key financial metrics from SEC XBRL data."""
    return sec_edgar.key_financials(cik)


def sec_gaap_fact(cik: str, fact_name: str, unit: str = "USD") -> list[dict]:
    """Get a specific GAAP fact history (e.g., 'Revenues', 'NetIncomeLoss')."""
    return sec_edgar.gaap_fact(cik, fact_name, unit)


# ═══════════════════════════════════════════════════════════════
# Layer 5: 资金面层 (Capital Flow)
# ═══════════════════════════════════════════════════════════════

def fund_flow(code: str, days: int = 20) -> dict:
    """Get US stock daily fund flow (主力/大单/中单/小单).

    Uses Eastmoney push2his API.
    code format: '105.AAPL' (NASDAQ), '106.XOM' (NYSE)
    """
    return eastmoney.fund_flow(code, days)


# ═══════════════════════════════════════════════════════════════
# Layer 6: 期权层 (Options)
# ═══════════════════════════════════════════════════════════════

def options_chain(symbol: str, expiration: str | None = None) -> dict:
    """Get options chain with Greeks (US stocks only)."""
    return yahoo.options_chain(symbol, expiration)


# ═══════════════════════════════════════════════════════════════
# Layer 7: SEC Filing 层
# ═══════════════════════════════════════════════════════════════

def sec_filings(cik: str, form_types: list[str] | None = None,
                count: int = 20) -> list[dict]:
    """Get recent SEC filings (10-K, 10-Q, 8-K)."""
    if form_types is None:
        form_types = ["10-K", "10-Q", "8-K"]
    return sec_edgar.recent_filings(cik, form_types, count)


def ticker_to_cik(ticker: str) -> str:
    """Convert ticker to SEC CIK."""
    return sec_edgar.ticker_to_cik(ticker)


def cik_to_ticker(cik: str) -> str:
    """Convert CIK to ticker."""
    return sec_edgar.cik_to_ticker(cik)


def filing_document(url: str) -> str:
    """Download a filing document."""
    return sec_edgar.filing_document(url)


# ═══════════════════════════════════════════════════════════════
# Layer 8: 工具层 (Tools)
# ═══════════════════════════════════════════════════════════════

def search(keyword: str, count: int = 10) -> list[dict]:
    """Search US stocks by keyword."""
    return yahoo.search(keyword, count)


def market_list() -> list[dict]:
    """Get full US stock list (NASDAQ + NYSE)."""
    key = "us_stock_list"
    cached = _cache.get_json(key)
    if cached:
        return cached
    result = eastmoney.us_stock_list()
    if result:
        _cache.set_json(key, result)
    return result


# ═══════════════════════════════════════════════════════════════
# Helper functions for technical indicators
# ═══════════════════════════════════════════════════════════════

import numpy as np


def _sma(arr: np.ndarray, period: int) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=np.float64)
    if len(arr) >= period:
        cumsum = np.cumsum(np.insert(arr, 0, 0))
        result[period - 1:] = (cumsum[period:] - cumsum[:-period]) / period
    return result


def _ema(arr: np.ndarray, period: int) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=np.float64)
    if len(arr) < period:
        return result
    result[period - 1] = np.mean(arr[:period])
    multiplier = 2.0 / (period + 1)
    for i in range(period, len(arr)):
        result[i] = (arr[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


def _rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = _ema(gain, period)
    avg_loss = _ema(loss, period)
    rs = np.divide(avg_gain, avg_loss, out=np.full_like(avg_gain, np.nan), where=avg_loss != 0)
    return 100.0 - (100.0 / (1.0 + rs))


def _kdj(high: np.ndarray, low: np.ndarray, close: np.ndarray,
         n: int = 9) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = len(close)
    k = np.full(n, 50.0, dtype=np.float64)
    d = np.full(n, 50.0, dtype=np.float64)
    j = np.full(n, 50.0, dtype=np.float64)

    for i in range(8, n):
        hh = np.max(high[i - 8:i + 1])
        ll = np.min(low[i - 8:i + 1])
        rsv = ((close[i] - ll) / (hh - ll)) * 100 if hh != ll else 50
        k[i] = 2 / 3 * k[i - 1] + 1 / 3 * rsv
        d[i] = 2 / 3 * d[i - 1] + 1 / 3 * k[i]
        j[i] = 3 * k[i] - 2 * d[i]
    return k, d, j


def _rolling_std(arr: np.ndarray, period: int) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=np.float64)
    for i in range(period - 1, len(arr)):
        result[i] = np.std(arr[i - period + 1:i + 1], ddof=0)
    return result
