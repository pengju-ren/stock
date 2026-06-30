"""Baostock data vendor.

Covers: A-stock list, daily/weekly/monthly K-line (with PE/PB),
financial statements, industry classification, valuation data, dividends.

Source: baostock.com (HTTP API, free, registration required for full access)
Rate limit: None (generous free tier).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import pandas as pd
import baostock as bs

logger = logging.getLogger(__name__)

_logged_in = False


def _ensure_login():
    """Lazy login to baostock (auto-refresh)."""
    global _logged_in
    if not _logged_in:
        lg = bs.login()
        if lg.error_code != "0":
            logger.warning("baostock login failed: %s", lg.error_msg)
        else:
            _logged_in = True
    return _logged_in


# ---------------------------------------------------------------------------
# Stock list
# ---------------------------------------------------------------------------

def all_stocks(date: str = "") -> pd.DataFrame:
    """Get all A-share stock list for a given date.

    Returns DataFrame with: code, code_name, ipoDate, outDate, type, status.
    """
    _ensure_login()
    rs = bs.query_stock_basic(code_name="")
    if rs.error_code != "0":
        return pd.DataFrame()
    data = []
    while (rs.error_code == "0") & rs.next():
        data.append(rs.get_row_data())
    return pd.DataFrame(data, columns=rs.fields)


# ---------------------------------------------------------------------------
# K-line (daily/weekly/monthly)
# ---------------------------------------------------------------------------

def kline(code: str, start_date: str, end_date: str,
          frequency: str = "d", adjust: str = "2") -> pd.DataFrame:
    """Get historical K-line from baostock.

    Args:
        code: 6-digit stock code with market prefix (e.g., 'sh.600519')
        start_date: 'YYYY-MM-DD'
        end_date: 'YYYY-MM-DD'
        frequency: 'd'=daily, 'w'=weekly, 'm'=monthly, '5'=5min, '15'=15min, '30'=30min, '60'=60min
        adjust: '1'=后复权, '2'=前复权, '3'=不复权

    Returns:
        DataFrame with: date, code, open, high, low, close, preclose,
        volume, amount, adjustflag, turn, tradestatus, pctChg, peTTM, pbMRQ,
        psTTM, pcfNcfTTM, isST
    """
    _ensure_login()
    full_code = _to_bs_code(code)
    rs = bs.query_history_k_data_plus(
        full_code,
        "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST",
        start_date=start_date, end_date=end_date,
        frequency=frequency, adjustflag=adjust,
    )
    if rs.error_code != "0":
        return pd.DataFrame()
    data = []
    while (rs.error_code == "0") & rs.next():
        data.append(rs.get_row_data())
    df = pd.DataFrame(data, columns=rs.fields)
    for col in ["open", "high", "low", "close", "preclose", "volume", "amount",
                "turn", "pctChg", "peTTM", "pbMRQ", "psTTM", "pcfNcfTTM"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


def daily_kline(code: str, start_date: str = "2020-01-01",
                end_date: str = "", adjust: str = "2") -> pd.DataFrame:
    """Convenience: daily K-line."""
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    return kline(code, start_date, end_date, frequency="d", adjust=adjust)


# ---------------------------------------------------------------------------
# Financial data
# ---------------------------------------------------------------------------

def financials(code: str, year: int, quarter: int) -> pd.DataFrame:
    """Get quarterly financial data (利润表/资产负债表/现金流量表).

    Args:
        code: stock code
        year: fiscal year
        quarter: 1-4

    Returns:
        DataFrame with all financial statement fields
    """
    _ensure_login()
    full_code = _to_bs_code(code)
    rs = bs.query_growth_data(code=full_code, year=year, quarter=quarter)
    if rs.error_code != "0":
        return pd.DataFrame()
    data = []
    while (rs.error_code == "0") & rs.next():
        data.append(rs.get_row_data())
    return pd.DataFrame(data, columns=rs.fields)


# ---------------------------------------------------------------------------
# Industry classification
# ---------------------------------------------------------------------------

def industry(code: str) -> dict:
    """Get industry classification for a stock."""
    _ensure_login()
    full_code = _to_bs_code(code)
    rs = bs.query_stock_industry(code=full_code)
    if rs.error_code != "0":
        return {}
    data = []
    while (rs.error_code == "0") & rs.next():
        data.append(rs.get_row_data())
    if data:
        return {
            "code": data[0][0] if len(data[0]) > 0 else "",
            "name": data[0][1] if len(data[0]) > 1 else "",
            "industry": data[0][2] if len(data[0]) > 2 else "",
            "update_date": data[0][3] if len(data[0]) > 3 else "",
        }
    return {}


# ---------------------------------------------------------------------------
# Dividends
# ---------------------------------------------------------------------------

def dividends(code: str) -> pd.DataFrame:
    """Get dividend history."""
    _ensure_login()
    full_code = _to_bs_code(code)
    rs = bs.query_dividend_data(code=full_code, year="", yearType="report")
    if rs.error_code != "0":
        return pd.DataFrame()
    data = []
    while (rs.error_code == "0") & rs.next():
        data.append(rs.get_row_data())
    return pd.DataFrame(data, columns=rs.fields)


# ---------------------------------------------------------------------------
# Valuation (PE/PB band)
# ---------------------------------------------------------------------------

def valuation_history(code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Get historical valuation data (PE/PB/PS bands)."""
    _ensure_login()
    full_code = _to_bs_code(code)
    rs = bs.query_history_k_data_plus(
        full_code,
        "date,code,peTTM,pbMRQ,psTTM,pcfNcfTTM",
        start_date=start_date, end_date=end_date,
        frequency="d", adjustflag="2",
    )
    if rs.error_code != "0":
        return pd.DataFrame()
    data = []
    while (rs.error_code == "0") & rs.next():
        data.append(rs.get_row_data())
    df = pd.DataFrame(data, columns=rs.fields)
    for col in ["peTTM", "pbMRQ", "psTTM", "pcfNcfTTM"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_bs_code(code: str) -> str:
    """Convert 6-digit code to baostock format (sh.600519)."""
    code = str(code).strip()
    if "." in code:
        return code  # already formatted
    if code.startswith(("6", "9")):
        return f"sh.{code}"
    elif code.startswith("8") or code.startswith("4"):
        return f"bj.{code}"
    return f"sz.{code}"


def health_check() -> bool:
    """Quick connectivity test."""
    try:
        lg = bs.login()
        ok = lg.error_code == "0"
        bs.logout()
        return ok
    except Exception:
        return False
