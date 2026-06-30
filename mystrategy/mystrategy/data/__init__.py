"""Unified data layer for mystrategy.

Provides:
    - Vendor modules: direct access to individual data sources
    - Market APIs: unified interfaces per market (A-stock, US, HK)
    - Router: automatic vendor selection with fallback chains
    - Cache: local CSV/JSON caching with TTL

Usage:
    from mystrategy.data import a_stock, us_stock, hk_stock
    from mystrategy.data import get_router, get_cache

    # Unified market API (recommended)
    df = a_stock.kline("600519", days=250)
    quote = us_stock.realtime("AAPL")

    # Router with fallback
    router = get_router()
    data = router.route("a_stock", "kline", code="600519")
"""

from mystrategy.data import vendor
from mystrategy.data.cache import DataCache, get_cache
from mystrategy.data.router import DataRouter, get_router
from mystrategy.data.markets import a_stock, us_stock, hk_stock

__all__ = [
    "vendor",
    "DataCache", "get_cache",
    "DataRouter", "get_router",
    "a_stock", "us_stock", "hk_stock",
]
