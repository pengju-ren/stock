"""Data vendors — raw data source implementations.

Each vendor is a standalone module with a consistent interface:
    vendor.health_check() -> bool
    vendor.<method>(...) -> data

Vendors by source:
    eastmoney   — 东方财富 (HTTP, throttled)
    tencent     — 腾讯财经 (HTTP, no rate limit)
    sina        — 新浪财经 (HTTP, minimal rate limit)
    mootdx      — 通达信 TCP (TCP 7709, no rate limit)
    tonghuashun — 同花顺/10jqka (HTTP, moderate rate limit)
    cninfo      — 巨潮资讯 (HTTP, minimal rate limit)
    yahoo       — Yahoo Finance v8 (HTTP, moderate rate limit)
    sec_edgar   — SEC EDGAR (HTTP, 10 req/s limit)
    baostock    — Baostock (HTTP, free tier)
"""

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

__all__ = [
    "eastmoney",
    "tencent",
    "sina",
    "mootdx",
    "tonghuashun",
    "cninfo",
    "yahoo",
    "sec_edgar",
    "baostock",
]
