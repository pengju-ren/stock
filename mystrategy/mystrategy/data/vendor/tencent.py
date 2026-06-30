"""Tencent Finance (腾讯财经) data vendor.

Covers: real-time quotes, PE/PB/market cap/turnover, index data, K-line.

Source: qt.gtimg.cn (HTTP, GBK encoding)
Rate limit: None (实测不封IP)
"""

from __future__ import annotations

import re as _re
import urllib.request
import json


def _get_prefix(code: str) -> str:
    """6-digit A-stock code -> market prefix for Tencent API."""
    code = str(code).strip()
    if code.startswith(("6", "9")):
        return "sh"
    elif code.startswith("8") or code.startswith("4"):
        return "bj"
    return "sz"


def _normalize_ts_code(code: str) -> str:
    """Normalize a ticker to Tencent format: 'sh600519'."""
    code = str(code).strip().upper()
    for suffix in (".SH", ".SZ", ".BJ"):
        if code.endswith(suffix):
            code = code[:-len(suffix)]
    for prefix in ("SH", "SZ", "BJ"):
        if code.startswith(prefix):
            code = code[len(prefix):]
    return f"{_get_prefix(code)}{code}"


def realtime_quotes(codes: list[str]) -> dict[str, dict]:
    """Batch real-time quotes from Tencent Finance.

    Max ~50 codes per request. Returns dict keyed by 6-digit code.

    Fields returned:
        name, price, last_close, open, high, low, change_pct,
        turnover_pct, pe_ttm, pb, market_cap, float_mcap,
        limit_up, limit_down, pe_static, volume, amount
    """
    prefixed = [_normalize_ts_code(c) for c in codes]

    # Batch requests — 50 per call
    result = {}
    for i in range(0, len(prefixed), 50):
        batch = prefixed[i:i + 50]
        url = "https://qt.gtimg.cn/q=" + ",".join(batch)
        req = urllib.request.Request(url)
        req.add_header("User-Agent",
                       "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            raw = resp.read().decode("gbk")
        except Exception:
            continue

        for line in raw.strip().split("\n"):
            if not line.strip() or '="";' in line:
                continue
            m = _re.match(r'v_(\w+)="(.+)"', line)
            if not m:
                continue
            key = m.group(1)  # e.g., sh600519
            vals = m.group(2).split("~")
            if len(vals) < 53:
                continue
            # Extract 6-digit code from key
            code = key[2:] if len(key) > 2 else key
            result[code] = {
                "name": vals[1],
                "price": _float(vals[3]),
                "last_close": _float(vals[4]),
                "open": _float(vals[5]),
                "high": _float(vals[33]),
                "low": _float(vals[34]),
                "volume": _float(vals[6]),
                "amount": _float(vals[37]),
                "change_pct": _float(vals[32]),
                "turnover_pct": _float(vals[38]),
                "pe_ttm": _float(vals[39]),
                "pb": _float(vals[46]),
                "market_cap": _float(vals[45]),  # 市值 (亿)
                "float_mcap": _float(vals[44]),
                "limit_up": _float(vals[47]),
                "limit_down": _float(vals[48]),
                "pe_static": _float(vals[52]),
            }
    return result


def single_quote(code: str) -> dict:
    """Get a single stock's real-time quote."""
    result = realtime_quotes([code])
    return result.get(str(code).strip(), {})


def index_quotes(codes: list[str]) -> dict[str, dict]:
    """Get index quotes (上证指数/深证成指/创业板指 etc.).

    Use codes like: 'sh000001' (上证指数), 'sz399001' (深证成指)
    """
    url = "https://qt.gtimg.cn/q=" + ",".join(codes)
    req = urllib.request.Request(url)
    req.add_header("User-Agent",
                   "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        raw = resp.read().decode("gbk")
    except Exception:
        return {}

    result = {}
    for line in raw.strip().split("\n"):
        if not line.strip() or '="";' in line:
            continue
        m = _re.match(r'v_(\w+)="(.+)"', line)
        if not m:
            continue
        key = m.group(1)
        vals = m.group(2).split("~")
        if len(vals) < 32:
            continue
        result[key] = {
            "name": vals[1],
            "price": _float(vals[3]),
            "change_pct": _float(vals[32]),
            "change": _float(vals[31]),
            "high": _float(vals[33]),
            "low": _float(vals[34]),
            "volume": _float(vals[6]),
            "amount": _float(vals[37]),
        }
    return result


def valuation_snapshot(code: str) -> dict:
    """Quick valuation snapshot for a single stock."""
    q = single_quote(code)
    return {
        "name": q.get("name", ""),
        "price": q.get("price", 0),
        "pe_ttm": q.get("pe_ttm", 0),
        "pe_static": q.get("pe_static", 0),
        "pb": q.get("pb", 0),
        "market_cap": q.get("market_cap", 0),
        "turnover_pct": q.get("turnover_pct", 0),
        "change_pct": q.get("change_pct", 0),
    }


def health_check() -> bool:
    """Quick connectivity test."""
    try:
        url = "https://qt.gtimg.cn/q=sh600519"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status == 200
    except Exception:
        return False


def _float(val: str) -> float:
    """Safe float conversion."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0
