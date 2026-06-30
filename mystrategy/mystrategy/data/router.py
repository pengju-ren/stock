"""Data source router — routes requests to vendors with fallback chains.

Uses priority-ordered vendor lists from config. When the primary vendor
fails, it automatically falls back to the next one in the chain.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from mystrategy.config import A_STOCK_ROUTING, US_STOCK_ROUTING, HK_STOCK_ROUTING
from mystrategy.data.vendor import (
    eastmoney,
    tencent,
    sina,
    mootdx,
    tonghuashun,
    cninfo,
    yahoo,
    sec_edgar,
    baostock,
)

logger = logging.getLogger(__name__)

# Map vendor name to module
VENDOR_MAP = {
    "eastmoney": eastmoney,
    "tencent": tencent,
    "sina": sina,
    "mootdx": mootdx,
    "tonghuashun": tonghuashun,
    "cninfo": cninfo,
    "yahoo": yahoo,
    "sec_edgar": sec_edgar,
    "baostock": baostock,
}


class DataRouter:
    """Route data requests through vendor fallback chains.

    Usage:
        router = DataRouter()
        kline = router.route("a_stock", "kline", code="600519")
        quote = router.route("us_stock", "realtime", symbols=["AAPL"])
    """

    def __init__(self):
        self._routing = {
            "a_stock": A_STOCK_ROUTING,
            "us_stock": US_STOCK_ROUTING,
            "hk_stock": HK_STOCK_ROUTING,
        }
        self._vendor_health: dict[str, bool] = {}

    def _vendor_ok(self, vendor_name: str) -> bool:
        """Check if vendor is reachable (with caching)."""
        if vendor_name in self._vendor_health:
            return self._vendor_health[vendor_name]
        vendor = VENDOR_MAP.get(vendor_name)
        if vendor is None:
            return False
        try:
            ok = vendor.health_check()
            self._vendor_health[vendor_name] = ok
            return ok
        except Exception:
            self._vendor_health[vendor_name] = False
            return False

    def route(self, market: str, category: str, **kwargs) -> Any:
        """Route a data request through vendor fallback chain.

        Args:
            market: 'a_stock', 'us_stock', 'hk_stock'
            category: e.g., 'kline', 'realtime', 'financials', 'news', etc.
            **kwargs: passed to the vendor function

        Returns:
            Data from the first successful vendor, or None if all fail.

        Raises:
            ValueError if market or category is unknown.
        """
        routing = self._routing.get(market)
        if routing is None:
            raise ValueError(f"Unknown market: {market}")

        fallback_chain = routing.get(category)
        if fallback_chain is None:
            raise ValueError(f"Unknown data category '{category}' for market '{market}'")

        # Each vendor module has its own function names.
        # The category name maps to a standard function name.
        func_map = self._get_func_map(category)

        last_error = None
        for vendor_name in fallback_chain:
            if not self._vendor_ok(vendor_name):
                continue

            vendor = VENDOR_MAP[vendor_name]
            func_name = func_map.get(vendor_name, category)

            try:
                func = getattr(vendor, func_name, None)
                if func is None:
                    continue
                result = func(**kwargs)
                if result is not None and (not hasattr(result, 'empty') or not result.empty):
                    return result
            except Exception as e:
                last_error = e
                logger.debug("Vendor %s.%s failed: %s", vendor_name, func_name, e)
                continue

        if last_error:
            logger.warning("All vendors failed for %s/%s: %s", market, category, last_error)
        return None

    def _get_func_map(self, category: str) -> dict[str, str]:
        """Map category to vendor-specific function names.

        Different vendors use slightly different function names for the same
        logical operation. This maps them.
        """
        base_map = {
            "kline": {
                "sina": "kline", "mootdx": "daily_kline", "tencent": "realtime_quotes",
                "yahoo": "daily_kline", "baostock": "daily_kline", "eastmoney": "realtime_quotes",
            },
            "realtime": {
                "tencent": "single_quote", "sina": "realtime_quotes",
                "mootdx": "quotes", "eastmoney": "key_indicators",
                "yahoo": "realtime_quotes",
            },
            "financials": {
                "sina": "income_statement", "mootdx": "financial_snapshot",
                "eastmoney": "financial_statements", "yahoo": "key_statistics",
                "baostock": "financials",
            },
            "news": {
                "eastmoney": "stock_news", "tonghuashun": "hot_stocks",
            },
            "announcements": {
                "cninfo": "announcements",
            },
            "research_reports": {
                "eastmoney": "research_reports",
            },
            "fund_flow": {
                "eastmoney": "fund_flow",
            },
            "northbound_flow": {
                "tonghuashun": "northbound_flow",
            },
            "dragon_tiger": {
                "eastmoney": "dragon_tiger_board",
            },
            "lockup_expiry": {
                "eastmoney": "lockup_expiry",
            },
            "margin_trading": {
                "eastmoney": "margin_trading",
            },
            "block_trades": {
                "eastmoney": "block_trades",
            },
            "hot_stocks": {
                "tonghuashun": "hot_stocks",
            },
            "concept_blocks": {
                "tonghuashun": "concept_blocks",
            },
            "industry_comparison": {
                "eastmoney": "industry_comparison",
            },
            "limit_up_pool": {
                "eastmoney": "limit_up_pool",
            },
            "etf_options": {
                "sina": "etf_option_chain",
            },
            "sentiment": {
                "eastmoney": "hot_rank", "tonghuashun": "hot_rank",
            },
            "search": {
                "eastmoney": "search", "yahoo": "search",
            },
            "market_list": {
                "eastmoney": "a_stock_list",
            },
            "options": {
                "yahoo": "options_chain",
            },
            "sec_filings": {
                "sec_edgar": "recent_filings",
            },
        }
        return base_map.get(category, {})

    def invalidate_health_cache(self):
        """Clear health check cache to force re-probe."""
        self._vendor_health.clear()


# Global router instance
_router: DataRouter | None = None


def get_router() -> DataRouter:
    global _router
    if _router is None:
        _router = DataRouter()
    return _router
