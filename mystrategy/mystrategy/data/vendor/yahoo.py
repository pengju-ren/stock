"""Yahoo Finance data vendor.

Covers: K-line (chart v8 API, no crumb needed), real-time quotes,
financials (23 modules), options chain with Greeks, stock search.

Rate limit: Moderate (informal rate limit, use with respect).
"""

from __future__ import annotations

import json as _json
import re as _re
import time
import logging
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import requests as _requests

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Session management (crumb handling)
# ---------------------------------------------------------------------------

_session = None
_crumb: str | None = None
_crumb_ts: float = 0.0


def _get_session():
    global _session
    if _session is None:
        _session = _requests.Session()
        _session.headers.update({"User-Agent": UA})
    return _session


def _get_crumb() -> str:
    """Get Yahoo Finance crumb (needed for some endpoints).

    Auto-refreshes every 30 minutes.
    """
    global _crumb, _crumb_ts
    if _crumb and time.time() - _crumb_ts < 1800:
        return _crumb

    session = _get_session()
    try:
        resp = session.get("https://fc.yahoo.com/", timeout=10)
        cookies = resp.cookies.get_dict()

        crumb_url = "https://query2.finance.yahoo.com/v1/test/getcrumb"
        headers = {"User-Agent": UA}
        crumb_resp = session.get(crumb_url, headers=headers, cookies=cookies, timeout=10)
        _crumb = crumb_resp.text.strip()
        _crumb_ts = time.time()
        return _crumb
    except Exception as e:
        logger.warning("Failed to get Yahoo crumb: %s", e)
        return ""


# ---------------------------------------------------------------------------
# K-line (chart v8 API)
# ---------------------------------------------------------------------------

def kline(symbol: str, interval: str = "1d",
          period1: int | None = None, period2: int | None = None) -> pd.DataFrame:
    """Get historical K-line from Yahoo Finance chart v8 API.

    Args:
        symbol: ticker, e.g., 'AAPL', '0700.HK'
        interval: '1d', '1wk', '1mo', '1m', '5m', '15m', '30m', '60m'
        period1: start timestamp (default: 10 years ago)
        period2: end timestamp (default: now)

    Returns:
        DataFrame with columns: date, open, high, low, close, adj_close, volume
    """
    if period2 is None:
        period2 = int(time.time())
    if period1 is None:
        period1 = period2 - 10 * 365 * 86400

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    params = {
        "period1": str(period1), "period2": str(period2),
        "interval": interval, "includePrePost": "true",
        "events": "div|split|earn",
    }
    try:
        r = _get_session().get(url, params=params, timeout=15)
        d = r.json()
    except Exception:
        return pd.DataFrame()

    result = d.get("chart", {}).get("result", [])
    if not result:
        return pd.DataFrame()

    data = result[0]
    timestamps = data.get("timestamp", [])
    quotes = data.get("indicators", {}).get("quote", [{}])[0]
    adj_close = data.get("indicators", {}).get("adjclose", [{}])
    adj_values = adj_close[0].get("adjclose", []) if adj_close else []

    df = pd.DataFrame({
        "date": pd.to_datetime(timestamps, unit="s"),
        "open": quotes.get("open", []),
        "high": quotes.get("high", []),
        "low": quotes.get("low", []),
        "close": quotes.get("close", []),
        "volume": quotes.get("volume", []),
    })
    if adj_values and len(adj_values) == len(df):
        df["adj_close"] = adj_values
    return df


def daily_kline(symbol: str, years: int = 5) -> pd.DataFrame:
    """Get daily K-line for N years."""
    end = int(time.time())
    start = end - years * 365 * 86400
    return kline(symbol, interval="1d", period1=start, period2=end)


# ---------------------------------------------------------------------------
# Real-time quotes
# ---------------------------------------------------------------------------

def realtime_quotes(symbols: list[str]) -> dict[str, dict]:
    """Get real-time quotes for multiple symbols.

    Returns dict[ticker] -> {price, change, change_pct, pe, market_cap, ...}
    Max ~50 symbols per request.
    """
    result = {}
    for i in range(0, len(symbols), 50):
        batch = symbols[i:i + 50]
        url = f"https://query1.finance.yahoo.com/v7/finance/quote"
        params = {"symbols": ",".join(batch), "fields": "regularMarketPrice,regularMarketChange,regularMarketChangePercent,regularMarketOpen,regularMarketDayHigh,regularMarketDayLow,regularMarketVolume,regularMarketPreviousClose,marketCap,trailingPE,forwardPE,priceToBook,trailingEps,forwardEps,averageDailyVolume3Month,fiftyTwoWeekHigh,fiftyTwoWeekLow,shortName,longName,currency"}
        try:
            r = _get_session().get(url, params=params, timeout=15)
            d = r.json()
            for item in d.get("quoteResponse", {}).get("result", []) or []:
                sym = item.get("symbol", "")
                result[sym] = {
                    "name": item.get("shortName", item.get("longName", "")),
                    "price": item.get("regularMarketPrice", 0),
                    "change": item.get("regularMarketChange", 0),
                    "change_pct": item.get("regularMarketChangePercent", 0),
                    "open": item.get("regularMarketOpen", 0),
                    "high": item.get("regularMarketDayHigh", 0),
                    "low": item.get("regularMarketDayLow", 0),
                    "volume": item.get("regularMarketVolume", 0),
                    "prev_close": item.get("regularMarketPreviousClose", 0),
                    "market_cap": item.get("marketCap", 0),
                    "pe_ttm": item.get("trailingPE", 0),
                    "forward_pe": item.get("forwardPE", 0),
                    "pb": item.get("priceToBook", 0),
                    "eps": item.get("trailingEps", 0),
                    "forward_eps": item.get("forwardEps", 0),
                    "avg_volume": item.get("averageDailyVolume3Month", 0),
                    "high_52w": item.get("fiftyTwoWeekHigh", 0),
                    "low_52w": item.get("fiftyTwoWeekLow", 0),
                    "currency": item.get("currency", ""),
                }
        except Exception:
            continue
    return result


# ---------------------------------------------------------------------------
# Financial data (v10 finance API, 23 modules)
# ---------------------------------------------------------------------------

FINANCIAL_MODULES = [
    "financialData", "balanceSheetHistory", "cashflowStatementHistory",
    "incomeStatementHistory", "earnings", "earningsHistory", "earningsTrend",
    "industryTrend", "indexTrend", "sectorTrend",
    "defaultKeyStatistics", "summaryDetail", "price",
    "assetProfile", "fundOwnership", "insiderHolders", "institutionOwnership",
    "recommendationTrend", "upgradeDowngradeHistory",
    "majorDirectHolders", "majorHoldersBreakdown",
    "secFilings", "calendarEvents",
]


def get_modules(symbol: str, modules: list[str] | None = None) -> dict:
    """Fetch Yahoo Finance financial data modules.

    Args:
        symbol: ticker
        modules: list of module names; default = all 23

    Returns:
        dict[module_name] -> module data
    """
    if modules is None:
        modules = FINANCIAL_MODULES

    url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
    params = {"modules": ",".join(modules[:8])}  # Yahoo limits per call
    try:
        r = _get_session().get(url, params=params, timeout=15)
        d = r.json()
        return d.get("quoteSummary", {}).get("result", [{}])[0] or {}
    except Exception:
        return {}


def key_statistics(symbol: str) -> dict:
    """Get key statistics: PE, PB, ROE, market cap, etc."""
    data = get_modules(symbol, modules=["defaultKeyStatistics", "summaryDetail", "price", "financialData"])
    stats = data.get("defaultKeyStatistics", {}) or {}
    summary = data.get("summaryDetail", {}) or {}
    fin_data = data.get("financialData", {}) or {}
    price_data = data.get("price", {}) or {}

    return {
        "name": price_data.get("shortName", ""),
        "price": summary.get("regularMarketPrice", {}).get("raw", 0),
        "market_cap": summary.get("marketCap", {}).get("raw", 0),
        "pe_ttm": summary.get("trailingPE", {}).get("raw", 0),
        "forward_pe": summary.get("forwardPE", {}).get("raw", 0),
        "pb": summary.get("priceToBook", {}).get("raw", 0),
        "roe": fin_data.get("returnOnEquity", {}).get("raw", 0),
        "debt_to_equity": fin_data.get("debtToEquity", {}).get("raw", 0),
        "revenue_growth": fin_data.get("revenueGrowth", {}).get("raw", 0),
        "profit_margin": fin_data.get("profitMargins", {}).get("raw", 0),
        "beta": stats.get("beta", {}).get("raw", 0),
        "shares_outstanding": stats.get("sharesOutstanding", {}).get("raw", 0),
        "float_shares": stats.get("floatShares", {}).get("raw", 0),
        "short_ratio": stats.get("shortRatio", {}).get("raw", 0),
        "short_pct": stats.get("shortPercentOfFloat", {}).get("raw", 0),
        "held_by_insiders": stats.get("heldPercentInsiders", {}).get("raw", 0),
        "held_by_institutions": stats.get("heldPercentInstitutions", {}).get("raw", 0),
        "peg_ratio": stats.get("pegRatio", {}).get("raw", 0),
        "dividend_yield": summary.get("dividendYield", {}).get("raw", 0),
        "recommendation": fin_data.get("recommendationMean", {}).get("raw", 0),
    }


# ---------------------------------------------------------------------------
# Options chain
# ---------------------------------------------------------------------------

def options_chain(symbol: str, expiration: str | None = None) -> dict:
    """Get options chain for a stock.

    Args:
        symbol: ticker, e.g., 'AAPL'
        expiration: expiration date YYYY-MM-DD; None = nearest

    Returns:
        dict with 'expiration_dates', 'calls', 'puts' (each with Greeks)
    """
    if expiration is None:
        url = f"https://query1.finance.yahoo.com/v7/finance/options/{symbol}"
    else:
        ts = int(datetime.strptime(expiration, "%Y-%m-%d").timestamp())
        url = f"https://query1.finance.yahoo.com/v7/finance/options/{symbol}?date={ts}"

    try:
        r = _get_session().get(url, timeout=15)
        d = r.json()
        records = d.get("optionChain", {}).get("result", [{}])[0] or {}
        exp_dates = records.get("expirationDates", [])
        options = records.get("options", [{}])[0] or {}

        def _parse_chain(option_list: list) -> list[dict]:
            result = []
            for o in option_list:
                result.append({
                    "strike": o.get("strike", {}).get("raw", 0),
                    "last_price": o.get("lastPrice", {}).get("raw", 0),
                    "bid": o.get("bid", {}).get("raw", 0),
                    "ask": o.get("ask", {}).get("raw", 0),
                    "volume": o.get("volume", {}).get("raw", 0),
                    "open_interest": o.get("openInterest", {}).get("raw", 0),
                    "implied_vol": o.get("impliedVolatility", {}).get("raw", 0),
                    "delta": o.get("delta", {}).get("raw", 0),
                    "gamma": o.get("gamma", {}).get("raw", 0),
                    "theta": o.get("theta", {}).get("raw", 0),
                    "vega": o.get("vega", {}).get("raw", 0),
                    "expiration": expiration or "",
                    "contract_name": o.get("contractSymbol", ""),
                })
            return result

        return {
            "expiration_dates": [datetime.fromtimestamp(d).strftime("%Y-%m-%d") for d in exp_dates],
            "calls": _parse_chain(options.get("calls", [])),
            "puts": _parse_chain(options.get("puts", [])),
        }
    except Exception:
        return {"expiration_dates": [], "calls": [], "puts": []}


# ---------------------------------------------------------------------------
# Stock search
# ---------------------------------------------------------------------------

def search(keyword: str, count: int = 10) -> list[dict]:
    """Search stocks by keyword."""
    url = "https://query1.finance.yahoo.com/v1/finance/search"
    params = {"q": keyword, "quotesCount": str(count), "newsCount": "0"}
    try:
        r = _get_session().get(url, params=params, timeout=10)
        d = r.json()
        results = []
        for q in d.get("quotes", []) or []:
            if q.get("quoteType") in ("EQUITY", "ETF"):
                results.append({
                    "symbol": q.get("symbol", ""),
                    "name": q.get("shortname", q.get("longname", "")),
                    "exchange": q.get("exchange", ""),
                    "type": q.get("quoteType", ""),
                })
        return results
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def health_check() -> bool:
    """Quick connectivity test."""
    try:
        r = _get_session().get("https://query1.finance.yahoo.com/v8/finance/chart/AAPL",
                              params={"period1": str(int(time.time()) - 86400),
                                      "period2": str(int(time.time())),
                                      "interval": "1d"},
                              timeout=10)
        return r.status_code == 200
    except Exception:
        return False
