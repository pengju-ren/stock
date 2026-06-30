"""Global configuration — all tunable parameters in one place.

Modify this file to adjust factor weights, technical parameters, backtest settings, etc.
"""

import os
from pathlib import Path

# ============================================================
# Paths
# ============================================================
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = Path(os.environ.get("MYSTRATEGY_DATA_DIR", PROJECT_ROOT / "data"))
CACHE_DIR = DATA_DIR / "cache"
OUTPUT_DIR = Path(os.environ.get("MYSTRATEGY_OUTPUT_DIR", PROJECT_ROOT / "output"))
LOG_DIR = Path(os.environ.get("MYSTRATEGY_LOG_DIR", PROJECT_ROOT / "logs"))

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ============================================================
# Data source routing (priority order: first available wins)
# ============================================================
# A-stock data source fallback chains
A_STOCK_ROUTING = {
    "kline": ["mootdx", "sina", "tencent"],
    "realtime": ["tencent", "mootdx", "eastmoney"],
    "financials": ["mootdx", "sina", "eastmoney"],
    "news": ["eastmoney", "tonghuashun"],
    "announcements": ["cninfo"],
    "research_reports": ["eastmoney"],
    "fund_flow": ["eastmoney"],
    "northbound_flow": ["tonghuashun"],
    "dragon_tiger": ["eastmoney"],
    "lockup_expiry": ["eastmoney"],
    "margin_trading": ["eastmoney"],
    "block_trades": ["eastmoney"],
    "hot_stocks": ["tonghuashun"],
    "concept_blocks": ["tonghuashun"],
    "industry_comparison": ["eastmoney"],
    "limit_up_pool": ["eastmoney"],
    "etf_options": ["sina"],
    "sentiment": ["eastmoney", "tonghuashun"],
}

# US stock data source routing
US_STOCK_ROUTING = {
    "kline": ["sina", "yahoo"],
    "realtime": ["sina", "tencent", "eastmoney"],
    "financials": ["yahoo", "eastmoney", "sec_edgar"],
    "fund_flow": ["eastmoney"],
    "options": ["yahoo"],
    "sec_filings": ["sec_edgar"],
    "news": ["yahoo"],
    "search": ["eastmoney", "yahoo"],
    "market_list": ["eastmoney"],
}

# HK stock data source routing
HK_STOCK_ROUTING = {
    "kline": ["yahoo"],
    "realtime": ["tencent", "sina", "eastmoney"],
    "financials": ["yahoo", "eastmoney"],
    "fund_flow": ["eastmoney"],
    "search": ["eastmoney", "yahoo"],
    "market_list": ["eastmoney"],
}

# ============================================================
# Eastmoney anti-ban throttling
# ============================================================
EM_MIN_INTERVAL = float(os.environ.get("EM_MIN_INTERVAL", "1.0"))

# ============================================================
# Cache settings
# ============================================================
CACHE_ENABLED = os.environ.get("MYSTRATEGY_CACHE", "1") == "1"
CACHE_TTL_SECONDS = {
    "realtime": 3,        # Real-time quotes: 3 seconds
    "kline_daily": 3600,  # Daily K-line: 1 hour
    "kline_minute": 300,  # Minute K-line: 5 minutes
    "financials": 86400,  # Financial data: 1 day
    "news": 600,          # News: 10 minutes
    "fund_flow": 300,     # Fund flow: 5 minutes
}

# ============================================================
# Factor weights (3 major categories sum to 1.0)
# ============================================================
WEIGHTS = {
    "fundamentals": 0.40,
    "capital_flow": 0.30,
    "technical": 0.30,
}

# Fundamental sub-factor weights
FUNDAMENTAL_SUB_WEIGHTS = {
    "pe_rank": 0.15,
    "pb_rank": 0.10,
    "roe": 0.15,
    "profit_growth": 0.12,
    "revenue_growth": 0.10,
    "debt_ratio": 0.10,
    "cashflow_quality": 0.08,
    "revenue_qoq": 0.05,
    "profit_qoq": 0.05,
    "margin_trend": 0.03,
    "dupont": 0.07,
}

# Capital flow sub-factor weights
CAPITAL_FLOW_SUB_WEIGHTS = {
    "main_flow_5d": 0.25,
    "main_flow_20d": 0.20,
    "big_order_ratio": 0.20,
    "volume_price_match": 0.15,
    "north_flow": 0.20,
}

# Technical sub-factor weights (18 factors, 5 categories)
TECHNICAL_SUB_WEIGHTS = {
    # Trend (25%)
    "ma_alignment": 0.08,
    "ma_cross": 0.06,
    "adx_trend": 0.11,
    # Momentum (30%)
    "rsi_signal": 0.07,
    "macd_signal": 0.08,
    "cci_signal": 0.04,
    "willr_signal": 0.03,
    "mfi_signal": 0.04,
    "roc_signal": 0.04,
    # Volatility (15%)
    "bollinger_signal": 0.06,
    "atr_signal": 0.04,
    "keltner_signal": 0.03,
    "stddev_signal": 0.02,
    # Volume (20%)
    "volume_signal": 0.08,
    "obv_signal": 0.04,
    "adosc_signal": 0.04,
    "cmf_signal": 0.04,
    # Pattern (5%)
    "pattern_bullish": 0.03,
    "pattern_bearish": 0.02,
}

# ============================================================
# Technical indicator parameters
# ============================================================
MA_SHORT = 5
MA_MEDIUM = 20
MA_LONG = 60
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2

# ============================================================
# Backtest defaults
# ============================================================
BACKTEST_DEFAULTS = {
    "initial_capital": 1_000_000,
    "commission_rate": 0.0003,      # A-share: 0.03%
    "stamp_tax_rate": 0.001,        # Sell only: 0.1%
    "min_lot": 100,                 # A-share: 100 shares/lot
    "slippage": 0.001,              # 0.1% slippage
    "t_plus_1": True,               # A-share: T+1 settlement
    "price_limit_pct": 0.10,        # Main board: ±10%
    "benchmark": "000300",          # CSI 300
}

# ============================================================
# Portfolio defaults
# ============================================================
PORTFOLIO_DEFAULTS = {
    "max_single_position": 0.40,    # Max 40% in one stock
    "max_top3_position": 0.80,      # Max 80% in top 3
    "min_positions": 5,
    "max_positions": 15,
    "min_cash": 0.10,               # Min 10% cash
    "max_cash": 0.30,               # Max 30% cash
}

# ============================================================
# Research thresholds (from ai-berkshire)
# ============================================================
RESEARCH_THRESHOLDS = {
    # Quality screen: 7 hard indicators
    "min_roe_10yr": 8.0,            # 10-year avg ROE >= 8%
    "min_interest_coverage": 2.0,   # EBIT/Interest >= 2x
    "min_gross_margin": 15.0,       # Long-term gross margin >= 15%
    "min_ocf_to_np": 0.70,          # OCF/Net Profit 5yr avg >= 0.7
    "min_net_margin": 5.0,          # Long-term net margin >= 5%
    "max_share_dilution": 20.0,     # 5yr dilution (non-M&A) <= 20%
    # Funnel screening
    "max_debt_ratio": 60.0,         # Max debt ratio 60% (utilities 70%)
    "min_roe_improving": 15.0,      # ROE > 15% or improving 3yr trend
    "max_peg": 1.5,                 # PEG < 1.5 for growth companies
}

# ============================================================
# User-Agent for HTTP requests
# ============================================================
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
