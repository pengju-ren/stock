"""Sina Finance (新浪财经) data vendor.

Covers: K-line (daily, weekly, monthly, minute), real-time quotes,
financial statements (income/balance_sheet/cash_flow), ETF options.

Rate limit: Minimal (实测基本不封IP).
"""

from __future__ import annotations

import json as _json
import re as _re
from datetime import datetime
from typing import Any

import pandas as pd
import requests as _requests

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _get_prefix(code: str) -> str:
    """6-digit code -> market prefix for Sina API."""
    code = str(code).strip()
    if code.startswith(("6", "9")):
        return "sh"
    elif code.startswith("8") or code.startswith("4"):
        return "bj"
    return "sz"


# ---------------------------------------------------------------------------
# K-line (daily/weekly/monthly — Sina JS API)
# ---------------------------------------------------------------------------

def kline(code: str, period: str = "day", count: int = 500) -> pd.DataFrame:
    """Get historical K-line from Sina Finance JS API.

    Args:
        code: 6-digit stock code
        period: 'day', 'week', 'month', '5min', '15min', '30min', '60min'
        count: number of bars

    Returns:
        DataFrame with columns: date, open, high, low, close, volume
    """
    period_map = {
        "day": "day", "week": "week", "month": "month",
        "5min": "5", "15min": "15", "30min": "30", "60min": "60",
    }
    p = period_map.get(period, "day")
    prefix = _get_prefix(code)
    symbol = f"{prefix}{code}"

    url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData/getKLineData"
    params = {"symbol": symbol, "scale": str(count), "ma": "no", "datalen": str(count * 2)}

    try:
        r = _requests.get(url, params=params, headers={"User-Agent": UA}, timeout=15)
        data = r.json()
    except Exception:
        return pd.DataFrame()

    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    df = df.rename(columns={
        "day": "date", "open": "open", "high": "high",
        "low": "low", "close": "close", "volume": "volume",
    })
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


# ---------------------------------------------------------------------------
# Real-time quotes (hq.sinajs.cn)
# ---------------------------------------------------------------------------

def realtime_quotes(codes: list[str]) -> dict[str, dict]:
    """Get real-time quotes from Sina (hq.sinajs.cn).

    For A-shares; returns key indicators per stock.
    Max ~100 codes per request.
    """
    symbols = []
    for c in codes:
        c = str(c).strip()
        prefix = _get_prefix(c)
        symbols.append(f"{prefix}{c}")

    result = {}
    for i in range(0, len(symbols), 80):
        batch = symbols[i:i + 80]
        url = f"https://hq.sinajs.cn/list={','.join(batch)}"
        r = _requests.get(url, headers={
            "User-Agent": UA, "Referer": "https://finance.sina.com.cn",
        }, timeout=10)
        r.encoding = "gbk"

        for line in r.text.strip().split("\n"):
            if not line.strip():
                continue
            m = _re.match(r"var hq_str_(\w+)=\"(.+)\"", line)
            if not m:
                continue
            key = m.group(1)
            vals = m.group(2).split(",")
            if len(vals) < 33:
                continue
            code = key[2:]
            result[code] = {
                "name": vals[0],
                "open": _float(vals[1]),
                "last_close": _float(vals[2]),
                "price": _float(vals[3]),
                "high": _float(vals[4]),
                "low": _float(vals[5]),
                "volume": _float(vals[8]),
                "amount": _float(vals[9]),
                "change_pct": _float(vals[3]) / _float(vals[2]) - 1 if _float(vals[2]) else 0,
                "date": vals[30],
                "time": vals[31],
            }
    return result


# ---------------------------------------------------------------------------
# US stock real-time quotes
# ---------------------------------------------------------------------------

def us_realtime_quotes(codes: list[str]) -> dict[str, dict]:
    """Get US stock real-time/delayed quotes from Sina.

    Codes: e.g., 'AAPL', 'TSLA', 'MSFT'
    Max ~20 codes per request.
    """
    symbols = [f"gb_{c.strip().lower()}" for c in codes]
    result = {}
    for i in range(0, len(symbols), 20):
        batch = symbols[i:i + 20]
        url = f"https://hq.sinajs.cn/list={','.join(batch)}"
        r = _requests.get(url, headers={
            "User-Agent": UA, "Referer": "https://finance.sina.com.cn",
        }, timeout=10)
        r.encoding = "gbk"

        for line in r.text.strip().split("\n"):
            if not line.strip():
                continue
            m = _re.match(r"var hq_str_gb_(\w+)=\"(.+)\"", line)
            if not m:
                continue
            ticker = m.group(1).upper()
            vals = m.group(2).split(",")
            if len(vals) < 10:
                continue
            # Sina US quote format varies, parse adaptively
            result[ticker] = {
                "name": vals[0] if len(vals) > 0 else "",
                "price": _float(vals[1]) if len(vals) > 1 else 0,
                "change_pct": _float(vals[2]) if len(vals) > 2 else 0,
                "change": _float(vals[3]) if len(vals) > 3 else 0,
                "open": _float(vals[5]) if len(vals) > 5 else 0,
                "high": _float(vals[6]) if len(vals) > 6 else 0,
                "low": _float(vals[7]) if len(vals) > 7 else 0,
                "volume": _float(vals[10]) if len(vals) > 10 else 0,
                "pe_ttm": _float(vals[14]) if len(vals) > 14 else 0,
                "market_cap": _float(vals[16]) if len(vals) > 16 else 0,
            }
    return result


# ---------------------------------------------------------------------------
# HK stock real-time quotes
# ---------------------------------------------------------------------------

def hk_realtime_quotes(codes: list[str]) -> dict[str, dict]:
    """Get HK stock real-time/delayed quotes from Sina.

    Codes: e.g., '00700' (Tencent)
    """
    symbols = [f"hk{c.strip().zfill(5)}" for c in codes]
    result = {}
    for i in range(0, len(symbols), 20):
        batch = symbols[i:i + 20]
        url = f"https://hq.sinajs.cn/list={','.join(batch)}"
        r = _requests.get(url, headers={
            "User-Agent": UA, "Referer": "https://finance.sina.com.cn",
        }, timeout=10)
        r.encoding = "gbk"

        for line in r.text.strip().split("\n"):
            if not line.strip():
                continue
            m = _re.match(r"var hq_str_hk(\w+)=\"(.+)\"", line)
            if not m:
                continue
            code = m.group(1)
            vals = m.group(2).split(",")
            if len(vals) < 10:
                continue
            result[code] = {
                "name": vals[1] if len(vals) > 1 else "",
                "open": _float(vals[2]),
                "last_close": _float(vals[3]),
                "high": _float(vals[4]),
                "low": _float(vals[5]),
                "price": _float(vals[6]),
                "change_pct": _float(vals[8]),
                "volume": _float(vals[11]),
                "turnover": _float(vals[12]),
                "pe_ttm": _float(vals[15]),
                "market_cap": _float(vals[17]),
            }
    return result


# ---------------------------------------------------------------------------
# Financial statements (Sina API)
# ---------------------------------------------------------------------------

def income_statement(code: str, count: int = 5) -> pd.DataFrame:
    """Get multi-period income statement from Sina."""
    prefix = _get_prefix(code)
    symbol = f"{prefix}{code}"
    url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vFinanceSummary/stockid/{symbol}.phtml"
    try:
        r = _requests.get(url, headers={"User-Agent": UA}, timeout=15)
        r.encoding = "gbk"
        dfs = pd.read_html(r.text)
        income_table = None
        for df in dfs:
            cols = [str(c) for c in df.columns]
            if any("营业收入" in c or "利润" in c or "收入" in c for c in cols):
                income_table = df
                break
        return income_table if income_table is not None else dfs[0] if dfs else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def balance_sheet(code: str, count: int = 5) -> pd.DataFrame:
    """Get balance sheet from Sina."""
    prefix = _get_prefix(code)
    symbol = f"{prefix}{code}"

    url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_BalanceSheet/stockid/{symbol}/ctrl/part/displaytype/4.phtml"
    try:
        r = _requests.get(url, headers={"User-Agent": UA}, timeout=15)
        r.encoding = "gbk"
        dfs = pd.read_html(r.text)
        return dfs[0] if dfs else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def cash_flow_statement(code: str, count: int = 5) -> pd.DataFrame:
    """Get cash flow statement from Sina."""
    prefix = _get_prefix(code)
    symbol = f"{prefix}{code}"

    url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vFD_CashFlow/stockid/{symbol}/ctrl/part/displaytype/4.phtml"
    try:
        r = _requests.get(url, headers={"User-Agent": UA}, timeout=15)
        r.encoding = "gbk"
        dfs = pd.read_html(r.text)
        return dfs[0] if dfs else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# ETF Options (Sina hq.sinajs.cn)
# ---------------------------------------------------------------------------

def etf_option_chain(underlying: str = "510050") -> dict:
    """Get ETF option T-quote (T型报价) with Greeks.

    Args:
        underlying: ETF code, e.g., '510050' (50ETF), '510300' (300ETF),
                    '588000' (科创50ETF), '510500' (500ETF)

    Returns:
        dict with 'calls' and 'puts' lists, each containing Greeks.
    """
    # Map underlying ETF to option code prefix
    opt_prefix_map = {
        "510050": "OP_510050",  # 50ETF options
        "510300": "OP_510300",  # 300ETF options
        "588000": "OP_588000",  # STAR 50 ETF
        "510500": "OP_510500",  # 500ETF options
    }
    prefix = opt_prefix_map.get(underlying, f"OP_{underlying}")

    # Fetch all option contracts for this underlying
    url = f"https://hq.sinajs.cn/list={prefix}"
    try:
        r = _requests.get(url, headers={
            "User-Agent": UA, "Referer": "https://finance.sina.com.cn",
        }, timeout=10)
        r.encoding = "gbk"
    except Exception:
        return {"calls": [], "puts": []}

    calls, puts = [], []
    for line in r.text.strip().split("\n"):
        if not line.strip():
            continue
        m = _re.match(r"var hq_str_(\w+)=\"(.+)\"", line)
        if not m:
            continue
        code = m.group(1)
        vals = m.group(2).split(",")
        if len(vals) < 40:
            continue

        contract = {
            "code": code,
            "name": vals[0] if vals else "",
            "strike": _float(vals[37]),
            "price": _float(vals[2]),
            "volume": _float(vals[6]),
            "open_interest": _float(vals[40]) if len(vals) > 40 else 0,
            "premium": _float(vals[38]) if len(vals) > 38 else 0,
            "delta": _float(vals[13]) if len(vals) > 13 else 0,
            "gamma": _float(vals[14]) if len(vals) > 14 else 0,
            "theta": _float(vals[15]) if len(vals) > 15 else 0,
            "vega": _float(vals[16]) if len(vals) > 16 else 0,
            "implied_vol": _float(vals[39]) if len(vals) > 39 else 0,
            "expiry": vals[36] if len(vals) > 36 else "",
        }
        # Calls have 'C' in the option code, Puts have 'P'
        if "C" in code and "P" not in code:
            calls.append(contract)
        else:
            puts.append(contract)

    return {"calls": sorted(calls, key=lambda x: x["strike"]),
            "puts": sorted(puts, key=lambda x: x["strike"])}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _float(val: Any) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def health_check() -> bool:
    """Quick connectivity test."""
    try:
        r = _requests.get("https://hq.sinajs.cn/list=sh600519",
                          headers={"User-Agent": UA}, timeout=5)
        return r.status_code == 200
    except Exception:
        return False
