"""Tonghuashun (同花顺/10jqka) data vendor.

Covers: consensus EPS forecast, hot stocks, northbound capital flow,
concept/sector blocks, hot list ranking.

Rate limit: Moderate (国内网站，基本不封API IP).
"""

from __future__ import annotations

import re as _re
import json as _json
import time
import logging
from typing import Any

import pandas as pd
import requests as _requests

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Consensus EPS forecast
# ---------------------------------------------------------------------------

def eps_forecast(code: str) -> pd.DataFrame:
    """Fetch consensus EPS forecast from 同花顺.

    Returns DataFrame with columns: 年度, 预测机构数, 最小值, 均值, 最大值.
    """
    url = f"https://basic.10jqka.com.cn/new/{code}/worth.html"
    headers = {
        "User-Agent": UA,
        "Referer": "https://basic.10jqka.com.cn/",
    }
    try:
        r = _requests.get(url, headers=headers, timeout=15)
        r.encoding = "gbk"
        dfs = pd.read_html(r.text)
        for df in dfs:
            cols = [str(c) for c in df.columns]
            if any("每股收益" in c or "均值" in c for c in cols):
                return df
        return dfs[0] if dfs else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def forecast_summary(code: str) -> dict:
    """Get EPS forecast summary with forward PE/PEG calculation.

    Returns: {year, consensus_eps, forward_pe, cagr, peg, digestion_years}
    """
    df = eps_forecast(code)
    if df.empty:
        return {}

    try:
        # Parse the first forecast row
        row = df.iloc[0]
        year = str(row.get("年度", row.get("年份", "")))
        mean_eps = float(row.get("均值", row.get("预测均值", 0)))

        result = {"year": year, "consensus_eps": mean_eps}
        return result
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Hot stocks / strong stocks
# ---------------------------------------------------------------------------

def hot_stocks(count: int = 50) -> list[dict]:
    """Get hot/strong stocks from THS (强势股).

    Returns list of {code, name, price, change_pct, reason}.
    """
    url = "https://data.10jqka.com.cn/dataapi/rank/hotStocks"
    headers = {
        "User-Agent": UA,
        "Referer": "https://data.10jqka.com.cn/",
    }
    try:
        r = _requests.get(url, headers=headers, timeout=10)
        d = r.json()
        return d.get("data", []) or []
    except Exception:
        return []


def strong_stocks(board: str = "all", count: int = 50) -> list[dict]:
    """Get strong stocks from THS zx.10jqka.com.cn.

    Args:
        board: board code, 'all' for all markets
        count: max results
    """
    url = f"https://zx.10jqka.com.cn/data/strongStock/board/{board}/rank/{board}/ajax/1/free/1/"
    headers = {
        "User-Agent": UA,
        "Referer": "https://zx.10jqka.com.cn/",
    }
    try:
        r = _requests.get(url, headers=headers, timeout=10)
        d = r.json()
        return d.get("data", [])[:count] or []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Northbound capital flow (沪深港通)
# ---------------------------------------------------------------------------

def northbound_flow() -> dict:
    """Get real-time northbound capital flow (北向资金).

    Returns: {buy, sell, net, time}
    """
    url = "https://data.10jqka.com.cn/dataapi/hsgt/getHsgtIndex"
    headers = {
        "User-Agent": UA,
        "Referer": "https://data.10jqka.com.cn/",
    }
    try:
        r = _requests.get(url, headers=headers, timeout=10)
        d = r.json()
        data = d.get("data", {}) or {}
        return {
            "buy": float(data.get("buy", 0)),
            "sell": float(data.get("sell", 0)),
            "net": float(data.get("net", 0)),
            "time": data.get("time", ""),
        }
    except Exception:
        return {"buy": 0, "sell": 0, "net": 0, "time": ""}


def northbound_history(days: int = 30) -> list[dict]:
    """Get northbound flow history."""
    url = "https://data.10jqka.com.cn/dataapi/hsgt/getHsgtDaily"
    params = {"page": "1", "size": str(days)}
    headers = {
        "User-Agent": UA,
        "Referer": "https://data.10jqka.com.cn/",
    }
    try:
        r = _requests.get(url, params=params, headers=headers, timeout=10)
        d = r.json()
        return d.get("data", []) or []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Concept/sector blocks
# ---------------------------------------------------------------------------

def concept_blocks(code: str) -> list[str]:
    """Get concept/sector blocks for a stock.

    Returns list of concept names (e.g., ['人工智能', '芯片', '5G']).
    """
    url = f"https://basic.10jqka.com.cn/{code}/"
    headers = {
        "User-Agent": UA,
        "Referer": "https://basic.10jqka.com.cn/",
    }
    try:
        r = _requests.get(url, headers=headers, timeout=10)
        r.encoding = "gbk"
        # Extract concept blocks from HTML
        concepts = []
        for m in _re.finditer(r'href="/concept/(\d+)/".*?>(.+?)</a>', r.text):
            concepts.append(m.group(2))
        return concepts
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Hot list / ranking
# ---------------------------------------------------------------------------

def hot_rank(count: int = 50) -> list[dict]:
    """Get THS stock popularity ranking."""
    url = "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock"
    params = {"type": "hour", "field": "hot", "adcode": "", "market": "", "count": str(count)}
    headers = {
        "User-Agent": UA,
        "Referer": "https://dq.10jqka.com.cn/",
    }
    try:
        r = _requests.get(url, params=params, headers=headers, timeout=10)
        d = r.json()
        return d.get("data", []) or []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Industry comparison data
# ---------------------------------------------------------------------------

def industry_list() -> list[dict]:
    """Get THS industry/sector classification list."""
    url = "https://data.10jqka.com.cn/dataapi/industry/industryList"
    headers = {
        "User-Agent": UA,
        "Referer": "https://data.10jqka.com.cn/",
    }
    try:
        r = _requests.get(url, headers=headers, timeout=10)
        d = r.json()
        return d.get("data", []) or []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def health_check() -> bool:
    """Quick connectivity test for THS."""
    try:
        r = _requests.get("https://data.10jqka.com.cn/dataapi/rank/hotStocks",
                          headers={"User-Agent": UA}, timeout=5)
        return r.status_code == 200
    except Exception:
        return False
