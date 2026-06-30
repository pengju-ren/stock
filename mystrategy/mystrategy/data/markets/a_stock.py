"""A-stock (沪深北) unified market API.

Aggregates all A-stock data endpoints across vendors into a single clean interface.
10-layer architecture with 40+ endpoints.

Layers:
    1. 行情 — K-line, real-time quotes, indices, ETFs
    2. 研报 — Research reports, EPS forecasts
    3. 信号 — Hot stocks, northbound flow, dragon-tiger, lockup, industry
    4. 资金面 — Fund flow, margin trading, block trades, holder count
    5. 新闻 — Stock news, global 7x24 news
    6. 基础数据 — Financials, F10, stock info
    7. 公告 — Full-text announcement search
    8. 打板 — Limit-up/down pools, board sentiment
    9. ETF期权 — ETF option chains with Greeks
    10. 舆情互动 — Investor Q&A, hot rank, concept heat
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from mystrategy.data.vendor import (
    eastmoney,
    tencent,
    sina,
    mootdx,
    tonghuashun,
    cninfo,
)
from mystrategy.data.cache import get_cache
from mystrategy.data.router import get_router
from mystrategy.config import A_STOCK_ROUTING

_cache = get_cache()
_router = get_router()


# ═══════════════════════════════════════════════════════════════
# Layer 1: 行情层 (Market Data — 不封IP优先)
# ═══════════════════════════════════════════════════════════════

def kline(code: str, freq: str = "daily", count: int = 250) -> pd.DataFrame:
    """Get K-line data. Uses mootdx TCP (no rate limit).

    Args:
        code: 6-digit stock code
        freq: 'daily', 'weekly', 'monthly', '5min', '15min', '30min', '60min'
        count: number of bars
    """
    freq_map = {
        "daily": 9, "weekly": 6, "monthly": 7,
        "5min": 0, "15min": 1, "30min": 2, "60min": 3,
    }
    f = freq_map.get(freq, 9)
    key = f"kline_a_{code}_{freq}_{count}"
    cached = _cache.get_df(key)
    if cached is not None:
        return cached

    try:
        df = mootdx.kline(code, freq=f, count=count)
    except Exception:
        df = sina.kline(code, period=freq, count=count)

    if not df.empty:
        _cache.set_df(key, df)
    return df


def realtime(codes: list[str]) -> dict[str, dict]:
    """Get real-time quotes with PE/PB/market cap. Uses Tencent (no rate limit)."""
    codes = [str(c).strip() for c in codes]
    key = f"rt_a_{'_'.join(codes[:5])}"
    cached = _cache.get_json(key)
    if cached is not None:
        return cached

    result = tencent.realtime_quotes(codes)
    if result:
        _cache.set_json(key, result)
    return result


def quote(code: str) -> dict:
    """Get single stock real-time quote."""
    result = realtime([code])
    return result.get(str(code).strip(), {})


def valuation(code: str) -> dict:
    """Quick valuation snapshot: PE, PB, market cap, turnover."""
    return tencent.valuation_snapshot(code)


def indices(codes: list[str]) -> dict[str, dict]:
    """Get index quotes (上证指数/深证成指/创业板指 etc)."""
    return tencent.index_quotes(codes)


def level2_quotes(symbols: list[str]) -> list[dict]:
    """Get Level-2 market depth (五档盘口 + 逐笔成交)."""
    return mootdx.quotes(symbols)


# ═══════════════════════════════════════════════════════════════
# Layer 2: 研报层 (Research Reports)
# ═══════════════════════════════════════════════════════════════

def research_reports(code: str, limit: int = 15) -> list[dict]:
    """Get analyst research reports for a stock."""
    return eastmoney.research_reports(code, limit=limit)


def eps_forecast(code: str) -> dict:
    """Get consensus EPS forecast from 同花顺."""
    return tonghuashun.forecast_summary(code)


# ═══════════════════════════════════════════════════════════════
# Layer 3: 信号层 (Signals)
# ═══════════════════════════════════════════════════════════════

def hot_stocks(count: int = 50) -> list[dict]:
    """Get hot/strong stocks (强势股)."""
    return tonghuashun.hot_stocks(count)


def northbound_flow() -> dict:
    """Get real-time northbound capital flow (北向资金)."""
    return tonghuashun.northbound_flow()


def concept_blocks(code: str) -> list[str]:
    """Get concept/sector blocks for a stock."""
    return tonghuashun.concept_blocks(code)


def industry_comparison(industry_code: str, sort: str = "f3",
                        count: int = 50) -> list[dict]:
    """Get all stocks in an industry ranked by metric."""
    return eastmoney.industry_comparison(industry_code, sort, count)


def dragon_tiger_board(code: str | None = None, days: int = 5) -> list[dict]:
    """Get dragon-tiger board (龙虎榜) data."""
    return eastmoney.dragon_tiger_board(code, days)


def lockup_expiry(code: str | None = None, days_ahead: int = 60) -> list[dict]:
    """Get upcoming lockup expiry (解禁) calendar."""
    return eastmoney.lockup_expiry(code, days_ahead)


# ═══════════════════════════════════════════════════════════════
# Layer 4: 资金面/筹码层 (Capital Flow & Chips)
# ═══════════════════════════════════════════════════════════════

def fund_flow(code: str, days: int = 20) -> dict:
    """Get stock fund flow (主力/大单/中单/小单)."""
    return eastmoney.fund_flow(code, days)


def margin_trading(code: str, days: int = 30) -> list[dict]:
    """Get margin trading (融资融券) history."""
    return eastmoney.margin_trading(code, days)


def block_trades(code: str | None = None, days: int = 30) -> list[dict]:
    """Get block trades (大宗交易)."""
    return eastmoney.block_trades(code, days)


def holder_count(code: str) -> list[dict]:
    """Get shareholder count history (股东户数)."""
    return eastmoney.holder_count(code)


def dividends(code: str) -> list[dict]:
    """Get dividend history (分红送转)."""
    return eastmoney.dividends(code)


# ═══════════════════════════════════════════════════════════════
# Layer 5: 新闻层 (News)
# ═══════════════════════════════════════════════════════════════

def stock_news(code: str, page_size: int = 15) -> list[dict]:
    """Get individual stock news."""
    return eastmoney.stock_news(code, page_size)


def global_news(page_size: int = 30) -> list[dict]:
    """Get global 7x24 financial news."""
    return eastmoney.global_news(page_size)


# ═══════════════════════════════════════════════════════════════
# Layer 6: 基础数据层 (Fundamentals)
# ═══════════════════════════════════════════════════════════════

def financial_snapshot(code: str) -> dict | None:
    """Get latest financial snapshot (EPS, BPS, ROE, etc)."""
    return mootdx.financial_snapshot(code)


def f10_overview(code: str) -> str:
    """Get F10 company overview text."""
    return mootdx.f10_overview(code)


def f10_industry(code: str) -> str:
    """Get F10 industry classification."""
    return mootdx.f10_industry(code)


def key_indicators(code: str) -> dict:
    """Get key stock indicators (PE/PB/ROE/EPS/market cap)."""
    return eastmoney.key_indicators(code)


def income_statement(code: str, count: int = 5) -> pd.DataFrame:
    """Get multi-period income statement."""
    return sina.income_statement(code, count)


def balance_sheet(code: str, count: int = 5) -> pd.DataFrame:
    """Get balance sheet."""
    return sina.balance_sheet(code, count)


def cash_flow_statement(code: str, count: int = 5) -> pd.DataFrame:
    """Get cash flow statement."""
    return sina.cash_flow_statement(code, count)


# ═══════════════════════════════════════════════════════════════
# Layer 7: 公告层 (Announcements)
# ═══════════════════════════════════════════════════════════════

def announcements(code: str, page_size: int = 10,
                  keyword: str = "", category: str = "") -> list[dict]:
    """Search company announcements (全文检索)."""
    return cninfo.announcements(code, page_size, keyword, category)


def announcement_detail(announcement_id: str) -> dict:
    """Get announcement full text."""
    return cninfo.announcement_detail(announcement_id)


# ═══════════════════════════════════════════════════════════════
# Layer 8: 打板层 (Board Trading)
# ═══════════════════════════════════════════════════════════════

def limit_up_pool(date: str = "") -> list[dict]:
    """Get today's limit-up board pool (涨停池)."""
    return eastmoney.limit_up_pool(date)


def limit_down_pool(date: str = "") -> list[dict]:
    """Get limit-down board pool (跌停池)."""
    return eastmoney.limit_down_pool(date)


def broken_board_pool(date: str = "") -> list[dict]:
    """Get broken board pool (炸板池)."""
    return eastmoney.broken_board_pool(date)


def yesterday_limit_up_pool(date: str = "") -> list[dict]:
    """Get yesterday's limit-up pool (昨日涨停池) for continuity."""
    return eastmoney.yesterday_limit_up_pool(date)


# ═══════════════════════════════════════════════════════════════
# Layer 9: ETF期权层 (ETF Options)
# ═══════════════════════════════════════════════════════════════

def etf_option_chain(underlying: str = "510050") -> dict:
    """Get ETF option T-quote with Greeks."""
    return sina.etf_option_chain(underlying)


# ═══════════════════════════════════════════════════════════════
# Layer 10: 舆情互动层 (Sentiment & IR)
# ═══════════════════════════════════════════════════════════════

def irm_qa(code: str, page_size: int = 20) -> list[dict]:
    """Get investor relations Q&A (互动易)."""
    return cninfo.irm_qa(code, page_size)


def hot_rank(page_size: int = 50) -> list[dict]:
    """Get stock popularity ranking (人气榜)."""
    return eastmoney.hot_rank(page_size)


def concept_hot_rank() -> list[dict]:
    """Get concept board popularity ranking (概念热度)."""
    return eastmoney.concept_hot_rank()


# ═══════════════════════════════════════════════════════════════
# Utility
# ═══════════════════════════════════════════════════════════════

def search(keyword: str, count: int = 10) -> list[dict]:
    """Search stocks by keyword (name or code)."""
    return eastmoney.search(keyword, count)


def market_list() -> list[dict]:
    """Get full A-share market list (沪深北)."""
    key = "a_stock_list"
    cached = _cache.get_json(key)
    if cached:
        return cached
    result = eastmoney.a_stock_list()
    if result:
        _cache.set_json(key, result)
    return result


def resolve_ticker(user_input: str) -> str:
    """Resolve Chinese name or code to 6-digit code."""
    return mootdx.resolve_ticker(user_input)
