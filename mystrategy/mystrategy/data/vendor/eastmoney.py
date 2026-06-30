"""Eastmoney (东方财富) data vendor.

Covers: real-time quotes, financials, news, fund flow, dragon-tiger board,
lockup expiry, margin trading, block trades, limit-up/down pools, sentiment.

ALL requests go through ThrottledSession to avoid IP bans.
Eastmoney rate limits: >5 req/s, >=10 concurrent, >=200 req/min → temp ban.
"""

from __future__ import annotations

import json as _json
import re as _re
import time
import uuid
from typing import Any

import requests as _requests

from mystrategy.config import UA, EM_MIN_INTERVAL
from mystrategy.data.vendor.base import ThrottledSession

# ---------------------------------------------------------------------------
# Global throttled session (shared across all Eastmoney calls)
# ---------------------------------------------------------------------------
_EM_SESSION: ThrottledSession | None = None


def _get_session() -> ThrottledSession:
    global _EM_SESSION
    if _EM_SESSION is None:
        _EM_SESSION = ThrottledSession(min_interval=EM_MIN_INTERVAL, user_agent=UA)
    return _EM_SESSION


def em_get(url: str, params: dict | None = None,
           headers: dict | None = None, timeout: int = 15, **kwargs):
    """Eastmoney throttled GET — single entry point for all EM HTTP calls."""
    return _get_session().get(url, params=params, headers=headers, timeout=timeout, **kwargs)


# ---------------------------------------------------------------------------
# Datacenter unified query
# ---------------------------------------------------------------------------

DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"


def datacenter_query(report_name: str, columns: str = "ALL",
                     filter_str: str = "", page_size: int = 50,
                     sort_columns: str = "", sort_types: str = "-1") -> list[dict]:
    """Generic Eastmoney datacenter query — used by dragon-tiger, lockup, etc."""
    r = em_get(DATACENTER_URL, params={
        "reportName": report_name, "columns": columns,
        "filter": filter_str, "pageNumber": "1", "pageSize": str(page_size),
        "sortColumns": sort_columns, "sortTypes": sort_types,
        "source": "WEB", "client": "WEB",
    }, timeout=15)
    d = r.json()
    return d.get("result", {}).get("data", []) if d.get("result") else []


# ---------------------------------------------------------------------------
# Stock news (search-api-web JSONP)
# ---------------------------------------------------------------------------

def stock_news(code: str, page_size: int = 15) -> list[dict]:
    """Get individual stock news from Eastmoney.

    Returns: [{title, content, time, source, url}]
    """
    url = "https://search-api-web.eastmoney.com/search/jsonp"
    inner = _json.dumps({
        "uid": "", "keyword": code, "type": ["cmsArticleWebOld"],
        "client": "web", "clientType": "web", "clientVersion": "curr",
        "param": {"cmsArticleWebOld": {
            "searchScope": "default", "sort": "default",
            "pageIndex": 1, "pageSize": page_size, "preTag": "", "postTag": "",
        }},
    }, separators=(",", ":"))
    hdrs = {"User-Agent": UA, "Referer": "https://so.eastmoney.com/"}
    r = em_get(url, params={"cb": "jQuery_news", "param": inner}, headers=hdrs, timeout=15)
    text = r.text
    d = _json.loads(text[text.index("(") + 1: text.rindex(")")])
    rows = []
    for a in d.get("result", {}).get("cmsArticleWebOld", []) or []:
        rows.append({
            "title": _re.sub(r"<[^>]+>", "", a.get("title", "")),
            "content": _re.sub(r"<[^>]+>", "", a.get("content", ""))[:200],
            "time": a.get("date", ""),
            "source": a.get("mediaName", ""),
            "url": a.get("url", ""),
        })
    return rows


# ---------------------------------------------------------------------------
# Global 7x24 news (np-weblist)
# ---------------------------------------------------------------------------

def global_news(page_size: int = 30) -> list[dict]:
    """Get global financial news (7x24 wire).

    Returns: [{title, content, time, source}]
    """
    url = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
    params = {
        "client": "web", "biz": "web_724", "fastColumn": "102", "sortEnd": "",
        "pageSize": str(page_size), "req_trace": str(uuid.uuid4()),
    }
    hdrs = {"User-Agent": UA, "Referer": "https://kuaixun.eastmoney.com/"}
    r = em_get(url, params=params, headers=hdrs, timeout=10)
    d = r.json()
    rows = []
    for item in d.get("data", {}).get("fastNewsList", []):
        rows.append({
            "title": item.get("title", ""),
            "content": (item.get("summary", "") or "")[:200],
            "time": item.get("showTime", ""),
            "source": "东财·全球资讯",
        })
    return rows


# ---------------------------------------------------------------------------
# Research reports (reportapi)
# ---------------------------------------------------------------------------

def research_reports(code: str, max_pages: int = 2, limit: int = 15) -> list[dict]:
    """Get analyst research reports for a stock."""
    REPORT_API = "https://reportapi.eastmoney.com/report/list"
    records: list[dict] = []
    for page in range(1, max_pages + 1):
        params = {
            "industryCode": "*", "pageSize": "50", "industry": "*",
            "rating": "*", "ratingChange": "*",
            "beginTime": "2000-01-01", "endTime": "2030-01-01",
            "pageNo": str(page), "fields": "", "qType": "0",
            "orgCode": "", "code": code, "rcode": "",
            "p": str(page), "pageNum": str(page), "pageNumber": str(page),
        }
        r = em_get(REPORT_API, params=params,
                   headers={"Referer": "https://data.eastmoney.com/"}, timeout=30)
        rows = r.json().get("data") or []
        if not rows:
            break
        records.extend(rows)
        if len(records) >= limit:
            break
    return records[:limit]


# ---------------------------------------------------------------------------
# Fund flow (push2)
# ---------------------------------------------------------------------------

def fund_flow(code: str, days: int = 20) -> dict:
    """Get stock fund flow (主力/超大单/大单/中单/小单).

    Returns dict with main_force_net, super_large_net, large_net, medium_net, small_net.
    """
    prefix = _get_em_prefix(code)
    secid = f"{prefix}.{code}"
    url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
    params = {
        "lmt": str(days), "klt": "101", "secid": secid,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
    }
    r = em_get(url, params=params, timeout=10)
    d = r.json()
    if not d.get("data") or not d["data"].get("klines"):
        return {}
    klines = d["data"]["klines"]
    result = {"daily": []}
    total_main = 0.0
    for line in klines:
        parts = line.split(",")
        if len(parts) < 7:
            continue
        main_net = float(parts[4]) if parts[4] != "-" else 0.0
        total_main += main_net
        result["daily"].append({
            "date": parts[0],
            "main_net": main_net,
            "super_large_net": float(parts[2]) if parts[2] != "-" else 0.0,
            "large_net": float(parts[3]) if parts[3] != "-" else 0.0,
            "medium_net": float(parts[5]) if parts[5] != "-" else 0.0,
            "small_net": float(parts[6]) if parts[6] != "-" else 0.0,
        })
    result["main_force_net_total"] = total_main
    return result


# ---------------------------------------------------------------------------
# Dragon-tiger board (datacenter)
# ---------------------------------------------------------------------------

def dragon_tiger_board(code: str | None = None, days: int = 5) -> list[dict]:
    """Get dragon-tiger board (龙虎榜) data.

    If code is None, returns all LHB records for recent days.
    """
    filter_str = ""
    if code:
        filter_str = f'(SECURITY_CODE="{code}")'
    return datacenter_query(
        report_name="RPT_DAILYBILLBOARD_DETAILSNEW",
        columns="ALL",
        filter_str=filter_str,
        page_size=50,
        sort_columns="TRADE_DATE",
        sort_types="-1",
    )


# ---------------------------------------------------------------------------
# Lockup expiry (datacenter)
# ---------------------------------------------------------------------------

def lockup_expiry(code: str | None = None, days_ahead: int = 60) -> list[dict]:
    """Get upcoming lockup expiry (解禁) calendar."""
    from datetime import datetime, timedelta
    start = datetime.now().strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
    filter_str = f'(UNFREEZE_DATE>=^{start}^ and UNFREEZE_DATE<=^{end}^)'
    if code:
        filter_str = f'(SECURITY_CODE="{code}") and {filter_str}'
    return datacenter_query(
        report_name="RPT_LIFTEDMARKET_NEXTTCLOSE",
        columns="ALL",
        filter_str=filter_str,
        page_size=100,
        sort_columns="UNFREEZE_DATE",
        sort_types="1",
    )


# ---------------------------------------------------------------------------
# Margin trading (datacenter)
# ---------------------------------------------------------------------------

def margin_trading(code: str, days: int = 30) -> list[dict]:
    """Get margin trading (融资融券) daily details."""
    from datetime import datetime, timedelta
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    filter_str = (
        f'(SECURITY_CODE="{code}")'
        f'(DATE>=^{start}^ and DATE<=^{end}^)'
    )
    return datacenter_query(
        report_name="RPTA_MARGIN_TRADINGDETAIL",
        columns="ALL",
        filter_str=filter_str,
        page_size=50,
        sort_columns="DATE",
        sort_types="-1",
    )


# ---------------------------------------------------------------------------
# Block trades (datacenter)
# ---------------------------------------------------------------------------

def block_trades(code: str | None = None, days: int = 30) -> list[dict]:
    """Get block trades (大宗交易)."""
    from datetime import datetime, timedelta
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    filter_str = f'(DEAL_DATE>=^{start}^ and DEAL_DATE<=^{end}^)'
    if code:
        filter_str = f'(SECURITY_CODE="{code}") and {filter_str}'
    return datacenter_query(
        report_name="RPT_BLOCKTRADE",
        columns="ALL",
        filter_str=filter_str,
        page_size=50,
        sort_columns="DEAL_DATE",
        sort_types="-1",
    )


# ---------------------------------------------------------------------------
# Holder count / shareholder stats (datacenter)
# ---------------------------------------------------------------------------

def holder_count(code: str) -> list[dict]:
    """Get shareholder count history (股东户数)."""
    filter_str = f'(SECURITY_CODE="{code}")'
    return datacenter_query(
        report_name="RPT_F10_EQUITY_ORGANIZATION",
        columns="ALL",
        filter_str=filter_str,
        page_size=20,
        sort_columns="END_DATE",
        sort_types="-1",
    )


# ---------------------------------------------------------------------------
# Dividends (datacenter)
# ---------------------------------------------------------------------------

def dividends(code: str) -> list[dict]:
    """Get dividend history (分红送转)."""
    filter_str = f'(SECURITY_CODE="{code}")'
    return datacenter_query(
        report_name="RPT_F10_DIVIDENDINFO",
        columns="ALL",
        filter_str=filter_str,
        page_size=20,
        sort_columns="DIVIDEND_YEAR",
        sort_types="-1",
    )


# ---------------------------------------------------------------------------
# Industry comparison (push2)
# ---------------------------------------------------------------------------

def industry_comparison(industry_code: str, sort: str = "f3", count: int = 50) -> list[dict]:
    """Get all stocks in an industry ranked by a metric.

    Args:
        industry_code: Eastmoney industry code (e.g., 'BK0477' for semiconductors)
        sort: sort field (f3=change_pct, f20=mcap, f9=pe)
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": str(count),
        "fs": f"b:{industry_code}+f:!200",
        "fields": "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f62,f115",
        "po": "1", "fid": sort,
    }
    r = em_get(url, params=params, timeout=10)
    d = r.json()
    return d.get("data", {}).get("diff", []) or []


# ---------------------------------------------------------------------------
# Limit-up/down pools (push2ex)
# ---------------------------------------------------------------------------

def limit_up_pool(date: str = "") -> list[dict]:
    """Get limit-up board pool (涨停池) for a given date.

    Args:
        date: YYYY-MM-DD format; empty = latest trading day.
    """
    url = "https://push2ex.eastmoney.com/getTopicZTPool"
    params = {
        "ut": "7eea3edcaed734bece6e2e35", "pageindex": "0", "pagesize": "200",
        "sort": "fbt:asc", "date": date,
    }
    r = em_get(url, params=params, timeout=10)
    d = r.json()
    return d.get("data", {}).get("pool", []) or []


def limit_down_pool(date: str = "") -> list[dict]:
    """Get limit-down board pool (跌停池)."""
    url = "https://push2ex.eastmoney.com/getTopicDTPool"
    params = {
        "ut": "7eea3edcaed734bece6e2e35", "pageindex": "0", "pagesize": "200",
        "sort": "fbt:asc", "date": date,
    }
    r = em_get(url, params=params, timeout=10)
    d = r.json()
    return d.get("data", {}).get("pool", []) or []


def broken_board_pool(date: str = "") -> list[dict]:
    """Get broken board pool (炸板池)."""
    url = "https://push2ex.eastmoney.com/getTopicZDPool"
    params = {
        "ut": "7eea3edcaed734bece6e2e35", "pageindex": "0", "pagesize": "200",
        "sort": "fbt:asc", "date": date,
    }
    r = em_get(url, params=params, timeout=10)
    d = r.json()
    return d.get("data", {}).get("pool", []) or []


def yesterday_limit_up_pool(date: str = "") -> list[dict]:
    """Get yesterday's limit-up pool (昨日涨停池) for continuity analysis."""
    url = "https://push2ex.eastmoney.com/getYesterdayZTPool"
    params = {
        "ut": "7eea3edcaed734bece6e2e35", "pageindex": "0", "pagesize": "200",
        "sort": "fbt:asc", "date": date,
    }
    r = em_get(url, params=params, timeout=10)
    d = r.json()
    return d.get("data", {}).get("pool", []) or []


# ---------------------------------------------------------------------------
# Sentiment / hot rank
# ---------------------------------------------------------------------------

def hot_rank(page_size: int = 50) -> list[dict]:
    """Get Eastmoney stock popularity ranking (人气榜)."""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": str(page_size),
        "fs": "m:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2",
        "fields": "f2,f3,f4,f12,f14",
        "po": "1", "fid": "f3",
    }
    r = em_get(url, params=params, timeout=10)
    d = r.json()
    return d.get("data", {}).get("diff", []) or []


def concept_hot_rank() -> list[dict]:
    """Get Eastmoney concept board popularity ranking (概念热度)."""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "50",
        "fs": "m:90+t:3+f:!50",
        "fields": "f2,f3,f4,f12,f14,f104,f105,f128",
        "po": "1", "fid": "f3",
    }
    r = em_get(url, params=params, timeout=10)
    d = r.json()
    return d.get("data", {}).get("diff", []) or []


# ---------------------------------------------------------------------------
# Stock search
# ---------------------------------------------------------------------------

def search(keyword: str, count: int = 10) -> list[dict]:
    """Search stocks by keyword (name or code)."""
    url = "https://searchapi.eastmoney.com/api/suggest/get"
    params = {"input": keyword, "type": "14", "token": "D43BF722C8E33BDC906FB84D85E326E8", "count": str(count)}
    r = em_get(url, params=params, timeout=10)
    d = r.json()
    return d.get("QuotationCodeTable", {}).get("Data", []) or []


# ---------------------------------------------------------------------------
# Full market stock list
# ---------------------------------------------------------------------------

def a_stock_list() -> list[dict]:
    """Get full A-share market list (沪深北, all listed stocks)."""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "6000",
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23",
        "fields": "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23",
    }
    r = em_get(url, params=params, timeout=30)
    d = r.json()
    return d.get("data", {}).get("diff", []) or []


def us_stock_list() -> list[dict]:
    """Get full US stock list."""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "10000",
        "fs": "m:105,m:106,m:107",
        "fields": "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23",
    }
    r = em_get(url, params=params, timeout=30)
    d = r.json()
    return d.get("data", {}).get("diff", []) or []


def hk_stock_list() -> list[dict]:
    """Get full HK stock list."""
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "20000",
        "fs": "m:128+t:3,m:128+t:4,m:128+t:1,m:128+t:2",
        "fields": "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23",
    }
    r = em_get(url, params=params, timeout=30)
    d = r.json()
    return d.get("data", {}).get("diff", []) or []


# ---------------------------------------------------------------------------
# Financial data (datacenter)
# ---------------------------------------------------------------------------

def financial_statements(code: str, report_type: str = "balance_sheet",
                         count: int = 5) -> list[dict]:
    """Get financial statements from Eastmoney datacenter.

    Args:
        code: 6-digit stock code
        report_type: 'balance_sheet', 'income_statement', 'cash_flow'
        count: number of recent reports
    """
    report_map = {
        "balance_sheet": "RPT_DMSK_FN_BALANCE",
        "income_statement": "RPT_DMSK_FN_INCOME",
        "cash_flow": "RPT_DMSK_FN_CASHFLOW",
    }
    report_name = report_map.get(report_type, report_type)
    filter_str = f'(SECURITY_CODE="{code}")'
    return datacenter_query(
        report_name=report_name,
        columns="ALL",
        filter_str=filter_str,
        page_size=count,
        sort_columns="NOTICE_DATE",
        sort_types="-1",
    )


# ---------------------------------------------------------------------------
# Key indicators (push2)
# ---------------------------------------------------------------------------

def key_indicators(code: str) -> dict:
    """Get key stock indicators (PE/PB/ROE/EPS/market cap/etc)."""
    prefix = _get_em_prefix(code)
    secid = f"{prefix}.{code}"
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    params = {
        "secid": secid,
        "fields": "f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f55,f57,f58,f60,f116,f117,f162,f167,f168,f169,f170,f171",
    }
    r = em_get(url, params=params, timeout=10)
    d = r.json().get("data", {}) or {}
    return {
        "name": d.get("f58", ""),
        "price": d.get("f43", 0) / 100 if d.get("f43") else 0,
        "change_pct": d.get("f170", 0) / 100 if d.get("f170") else 0,
        "pe_ttm": d.get("f162", 0) / 100 if d.get("f162") else 0,
        "pb": d.get("f167", 0) / 100 if d.get("f167") else 0,
        "market_cap": d.get("f116", 0),
        "total_shares": d.get("f43", 0),
        "roe": d.get("f171", 0) / 100 if d.get("f171") else 0,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_em_prefix(code: str) -> str:
    """Determine Eastmoney secid prefix from A-stock code."""
    code = str(code).strip()
    if code.startswith(("6", "9")):
        return "1"  # Shanghai
    elif code.startswith("8") or code.startswith("4"):
        return "0"  # Beijing
    return "0"  # Shenzhen (default)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def health_check() -> bool:
    """Quick connectivity test for Eastmoney."""
    try:
        r = em_get("https://push2.eastmoney.com/api/qt/stock/get",
                   params={"secid": "1.600519", "fields": "f43"}, timeout=5)
        return r.status_code == 200
    except Exception:
        return False
