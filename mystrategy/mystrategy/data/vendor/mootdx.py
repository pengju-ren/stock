"""Mootdx (通达信 TCP) data vendor.

Covers: K-line (daily/weekly/monthly/minute), financial snapshots, F10 text,
stock list (name→code mapping), real-time quotes with 5-level depth.

Protocol: TCP port 7709, no rate limit (不封IP).
Dependency: mootdx >= 0.10
"""

from __future__ import annotations

import logging
import socket
import re as _re
from functools import lru_cache

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known working TDX servers (verified 2026-06)
# ---------------------------------------------------------------------------
_TDX_SERVERS = [
    ("119.97.185.59", 7709), ("124.70.133.119", 7709), ("116.205.183.150", 7709),
    ("123.60.73.44", 7709), ("116.205.163.254", 7709), ("121.36.225.169", 7709),
    ("123.60.70.228", 7709), ("124.71.9.153", 7709), ("110.41.147.114", 7709),
    ("124.71.187.122", 7709),
]

_mootdx_client = None


def _probe_tdx(ip: str, port: int, timeout: float = 2.0) -> bool:
    """TCP handshake probe to check if TDX server is reachable."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def get_client():
    """Lazy-init robust mootdx Quotes client.

    Avoids mootdx 0.11.x BESTIP empty-string bug by:
    1. TCP-probing known server list first
    2. Falling back to bestip=True
    3. Falling back to plain factory (existing config may have cached IP)
    """
    global _mootdx_client
    if _mootdx_client is not None:
        return _mootdx_client

    from mootdx.quotes import Quotes

    for ip, port in _TDX_SERVERS:
        if _probe_tdx(ip, port):
            _mootdx_client = Quotes.factory(market="std", server=(ip, port))
            logger.info("mootdx connected: %s:%d", ip, port)
            return _mootdx_client

    try:
        _mootdx_client = Quotes.factory(market="std", bestip=True)
        return _mootdx_client
    except Exception:
        pass

    try:
        _mootdx_client = Quotes.factory(market="std")
        return _mootdx_client
    except Exception as e:
        raise RuntimeError(
            "mootdx 通达信服务器均不可达（TCP 7709）。海外网络通常全部超时，"
            f"请走国内代理或直接使用 6 位股票代码。原始错误：{e}"
        ) from e


def _normalize(code: str) -> str:
    """Normalize to pure 6-digit code."""
    code = str(code).strip().upper()
    code = _re.sub(r"\..*$", "", code)
    for prefix in ("SH", "SZ", "BJ"):
        if code.startswith(prefix):
            code = code[len(prefix):]
    return code


# ---------------------------------------------------------------------------
# K-line (日/周/月/分钟)
# ---------------------------------------------------------------------------

def kline(code: str, freq: int = 9, count: int = 100) -> pd.DataFrame:
    """Get K-line data via mootdx TCP.

    Args:
        code: 6-digit stock code
        freq: 0=5min, 1=15min, 2=30min, 3=1h, 6=weekly, 7=monthly, 9=daily
        count: number of bars to fetch

    Returns:
        DataFrame with columns: date, open, close, high, low, volume, amount
        Note: returns raw (non-adjusted) prices.
    """
    client = get_client()
    raw = client.bars(symbol=_normalize(code), frequency=freq, offset=0, count=count)
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw)
    df = df.rename(columns={
        "open": "open", "close": "close", "high": "high",
        "low": "low", "vol": "volume", "amount": "amount",
    })
    if "date" not in df.columns and "day" in df.columns:
        df["date"] = pd.to_datetime(df["day"])
    return df


def daily_kline(code: str, count: int = 250) -> pd.DataFrame:
    """Convenience: daily K-line."""
    return kline(code, freq=9, count=count)


def weekly_kline(code: str, count: int = 100) -> pd.DataFrame:
    """Convenience: weekly K-line."""
    return kline(code, freq=6, count=count)


def monthly_kline(code: str, count: int = 60) -> pd.DataFrame:
    """Convenience: monthly K-line."""
    return kline(code, freq=7, count=count)


# ---------------------------------------------------------------------------
# Real-time quotes (五档盘口 + 逐笔成交)
# ---------------------------------------------------------------------------

def quotes(symbols: list[str]) -> list[dict]:
    """Get real-time quotes with 5-level depth and tick data.

    No rate limit (TCP protocol, not HTTP).
    """
    client = get_client()
    return client.quotes(symbol=[_normalize(s) for s in symbols])


# ---------------------------------------------------------------------------
# Financial snapshot
# ---------------------------------------------------------------------------

def financial_snapshot(code: str) -> dict | None:
    """Get latest financial snapshot from mootdx.

    Returns dict with EPS, BPS, ROE, net profit, revenue, etc.
    """
    client = get_client()
    try:
        df = client.finance(symbol=_normalize(code))
        if df is None or df.empty:
            return None
        return df.iloc[0].to_dict()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# F10 overview text
# ---------------------------------------------------------------------------

def f10_overview(code: str) -> str:
    """Get F10 company overview text (业务/概念/主营)."""
    client = get_client()
    try:
        return client.f10(symbol=_normalize(code), kind="category")
    except Exception:
        return ""


def f10_industry(code: str) -> str:
    """Get F10 industry classification."""
    text = f10_overview(code)
    # Try to extract industry from the text
    for pattern in [r'所属行业[：:](.+)', r'行业[：:](.+)']:
        m = _re.search(pattern, text)
        if m:
            return m.group(1).strip()
    return ""


# ---------------------------------------------------------------------------
# Stock list (name <-> code mapping)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def build_name_code_map() -> tuple[dict[str, str], dict[str, str]]:
    """Build name→code and code→name maps for all A-stock listed companies.

    Returns:
        (name_to_code, code_to_name) — both dict[str, str]
    """
    client = get_client()
    n2c: dict[str, str] = {}
    c2n: dict[str, str] = {}

    for market in (0, 1):  # 0=SZ, 1=SH
        try:
            stocks = client.stocks(market=market)
            if stocks is None or stocks.empty:
                continue
            for _, row in stocks.iterrows():
                code = str(row["code"]).strip()
                name = str(row["name"]).strip()
                if not _re.match(r"^[0368]\d{5}$", code):
                    continue
                clean_name = name.replace(" ", "").replace("　", "")
                n2c[clean_name] = code
                c2n[code] = clean_name
        except Exception:
            continue

    logger.info("Built stock name-code map: %d entries", len(n2c))
    return n2c, c2n


def resolve_ticker(user_input: str) -> str:
    """Resolve user input (code or Chinese name) to 6-digit A-stock code.

    Accepts: '600519', 'SH600519', '600519.SH', '贵州茅台'
    Returns: '600519'
    Raises: ValueError if not resolvable.
    """
    s = user_input.strip()
    if not s:
        raise ValueError("输入不能为空")

    has_chinese = any("一" <= ch <= "鿿" for ch in s)

    if not has_chinese:
        return _normalize(s)

    clean = s.replace(" ", "").replace("　", "")
    n2c, _ = build_name_code_map()

    if clean in n2c:
        return n2c[clean]

    matches = {name: code for name, code in n2c.items() if clean in name}
    if len(matches) == 1:
        return next(iter(matches.values()))
    if len(matches) > 1:
        examples = ", ".join(f"{n}({c})" for n, c in list(matches.items())[:5])
        raise ValueError(f"'{s}' 匹配到多只股票: {examples}，请输入完整名称或代码")

    raise ValueError(f"找不到股票 '{s}'，请检查名称是否正确")


def health_check() -> bool:
    """Quick connectivity test — probes first available TDX server."""
    for ip, port in _TDX_SERVERS[:3]:
        if _probe_tdx(ip, port, timeout=2.0):
            return True
    return False
