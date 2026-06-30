"""HK stock (港股) unified market API.

Aggregates all HK stock data endpoints across vendors.
6-layer architecture with 12+ endpoints.

Layers:
    1. 行情 — Real-time/delayed quotes (Tencent, Sina, Eastmoney)
    2. K线 — Multi-period K-line (Yahoo chart v8)
    3. 技术指标 — MA/MACD/RSI/KDJ/Bollinger
    4. 基本面 — Financials, key indicators (Yahoo, Eastmoney)
    5. 资金面 — Daily fund flow (main force vs retail)
    6. 工具 — Stock search, market list
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from mystrategy.data.vendor import (
    eastmoney,
    tencent,
    sina,
    yahoo,
)
from mystrategy.data.cache import get_cache

_cache = get_cache()


# ═══════════════════════════════════════════════════════════════
# Layer 1: 行情层 (Market Data)
# ═══════════════════════════════════════════════════════════════

def realtime(codes: list[str]) -> dict[str, dict]:
    """Get real-time/delayed quotes for HK stocks.

    Uses Sina finance (free, no key needed).
    Codes: e.g., '00700' (Tencent)
    """
    return sina.hk_realtime_quotes(codes)


def quote(code: str) -> dict:
    """Get single stock quote."""
    result = realtime([code])
    return result.get(str(code).strip(), {})


# ═══════════════════════════════════════════════════════════════
# Layer 2: K线层 (K-line)
# ═══════════════════════════════════════════════════════════════

def kline(code: str, interval: str = "1d", years: int = 5) -> pd.DataFrame:
    """Get historical K-line from Yahoo Finance.

    Args:
        code: HK stock code, e.g., '0700.HK' or '00700'
        interval: '1d', '1wk', '1mo'
        years: years of history
    """
    # Normalize HK code to Yahoo format
    symbol = _to_yahoo_code(code)
    key = f"kline_hk_{symbol}_{interval}_{years}"
    cached = _cache.get_df(key)
    if cached is not None:
        return cached

    df = yahoo.daily_kline(symbol, years=years) if interval == "1d" else \
         yahoo.kline(symbol, interval=interval)

    if not df.empty:
        _cache.set_df(key, df)
    return df


def daily_kline(code: str, years: int = 5) -> pd.DataFrame:
    """Get daily K-line."""
    return kline(code, interval="1d", years=years)


# ═══════════════════════════════════════════════════════════════
# Layer 3: 技术指标层 (Technical Indicators)
# ═══════════════════════════════════════════════════════════════

def compute_indicators(code: str, years: int = 2) -> dict:
    """Compute technical indicators (MA, MACD, RSI, KDJ, Bollinger)."""
    df = daily_kline(code, years=years)
    if df.empty or len(df) < 60:
        return {}

    close = df["close"].values
    high = df["high"].values
    low = df["low"].values

    ma5 = _sma(close, 5)
    ma10 = _sma(close, 10)
    ma20 = _sma(close, 20)
    ma60 = _sma(close, 60)

    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    dif = ema12 - ema26
    dea = _ema(dif, 9)
    macd_bar = 2 * (dif - dea)

    k, d, j = _kdj(high, low, close, n=9)

    bb_mid = _sma(close, 20)
    bb_std = _rolling_std(close, 20)
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std

    return {
        "date": df["date"].values,
        "ma": {"ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60},
        "macd": {"dif": dif, "dea": dea, "bar": macd_bar},
        "rsi": {"rsi6": _rsi(close, 6), "rsi12": _rsi(close, 12), "rsi24": _rsi(close, 24)},
        "kdj": {"k": k, "d": d, "j": j},
        "bollinger": {"upper": bb_upper, "mid": bb_mid, "lower": bb_lower},
    }


# ═══════════════════════════════════════════════════════════════
# Layer 4: 基本面层 (Fundamentals)
# ═══════════════════════════════════════════════════════════════

def key_statistics(code: str) -> dict:
    """Get key statistics for HK stock.

    Uses Yahoo Finance with .HK suffix.
    """
    symbol = _to_yahoo_code(code)
    return yahoo.key_statistics(symbol)


def key_indicators(code: str) -> dict:
    """Get key indicators from Eastmoney (Chinese field names)."""
    # Eastmoney uses secid format: '116.00700'
    em_code = f"116.{code}"
    return eastmoney.key_indicators(em_code)


# ═══════════════════════════════════════════════════════════════
# Layer 5: 资金面层 (Capital Flow)
# ═══════════════════════════════════════════════════════════════

def fund_flow(code: str, days: int = 20) -> dict:
    """Get HK stock daily fund flow.

    Uses Eastmoney push2his. Code format: '116.00700'
    """
    em_code = f"116.{code}"
    return eastmoney.fund_flow(em_code, days)


# ═══════════════════════════════════════════════════════════════
# Layer 6: 工具层 (Tools)
# ═══════════════════════════════════════════════════════════════

def search(keyword: str, count: int = 10) -> list[dict]:
    """Search HK stocks by keyword.

    Tries Yahoo first, falls back to Eastmoney.
    """
    # Try Yahoo with .HK suffix
    results = yahoo.search(f"{keyword}.HK", count)
    if results:
        return results
    # Fallback: Eastmoney
    return eastmoney.search(keyword, count)


def market_list() -> list[dict]:
    """Get full HK stock list."""
    key = "hk_stock_list"
    cached = _cache.get_json(key)
    if cached:
        return cached
    result = eastmoney.hk_stock_list()
    if result:
        _cache.set_json(key, result)
    return result


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _to_yahoo_code(code: str) -> str:
    """Normalize HK stock code to Yahoo format (XXXX.HK)."""
    code = str(code).strip()
    if ".HK" in code.upper():
        return code
    code = code.replace(".", "").zfill(4) if code.isdigit() else code
    return f"{code}.HK"


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
    n_len = len(close)
    k = np.full(n_len, 50.0, dtype=np.float64)
    d = np.full(n_len, 50.0, dtype=np.float64)
    j = np.full(n_len, 50.0, dtype=np.float64)
    for i in range(8, n_len):
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
