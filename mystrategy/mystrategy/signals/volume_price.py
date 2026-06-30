"""Volume-price relationship signals.

Based on the "背个竹筐" teaching system, Episode 5:
    - 5 sell signals (放量滞涨, 缩量新高, 高位长上影, 放量大阴线, 反弹缩量)
    - 3 buy signals (缩量止跌, 放量突破, 低位地量)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from mystrategy.signals.base import Signal, SignalType, RiskLevel, ScanResult

# Default parameters
DEFAULT_PARAMS = {
    "volume_surge_ratio": 1.5,       # 放量：量比 > this
    "high_position_pct": 0.70,       # 高位分位数阈值
    "new_high_lookback": 60,         # 缩量新高回看天数
    "shrink_new_high_vol_pct": 0.7,  # 缩量新高成交量比例
    "bear_candle_pct": 3.0,          # 大阴线最小跌幅(%)
    "upper_shadow_ratio": 2.0,       # 长上影比例
    "bounce_shrink_vol_pct": 0.7,    # 反弹缩量比例
    "downtrend_lookback": 30,
    "volume_dry_up_ratio": 0.5,      # 地量：量 < 均量 * this
    "breakout_volume_ratio": 2.0,    # 放量突破量比
}


def scan_stock(df: pd.DataFrame, params: dict | None = None,
               name: str = "", market: str = "A") -> ScanResult:
    """Scan a single stock for volume-price signals.

    Args:
        df: OHLCV DataFrame with columns [date, open, high, low, close, volume]
        params: override default detection parameters
        name: stock name
        market: market identifier
    """
    p = {**DEFAULT_PARAMS, **(params or {})}

    if df.empty or len(df) < 60:
        return ScanResult(
            code=str(df.get("code", [None])[0] if "code" in df.columns else "?"),
            name=name, market=market,
        )

    code = str(df["code"].iloc[0]) if "code" in df.columns else "?"
    df = df.sort_values("date").reset_index(drop=True)

    close = df["close"].values.astype(np.float64)
    high = df["high"].values.astype(np.float64)
    low = df["low"].values.astype(np.float64)
    open_ = df["open"].values.astype(np.float64)
    volume = df["volume"].values.astype(np.float64)
    dates = df["date"].values

    n = len(close)

    # Pre-compute indicators
    vol_ratio = _volume_ratio(volume, 20)
    ema20 = _ema(close, 20)
    ema60 = _ema(close, 60)
    upper_shadow = _upper_shadow_ratio(high, open_, close)

    signals: list[Signal] = []

    # Scan each bar
    for i in range(60, n):
        is_high = is_price_high(close, i, p["high_position_pct"])
        is_low = _is_price_low(close, i, 0.30)
        in_downtrend = _is_downtrend(ema20, ema60, i)

        # ── 5 SELL signals ──

        # 1. 放量滞涨 (High Vol Flat)
        s = detect_high_vol_flat(close, vol_ratio, i, is_high, p, dates[i])
        if s: signals.append(s)

        # 2. 缩量新高 (Shrinking Vol New High)
        s = detect_shrink_new_high(close, volume, dates, i, p)
        if s: signals.append(s)

        # 3. 高位长上影 (High Long Upper Shadow)
        s = detect_high_long_upper_shadow(close, high, open_, vol_ratio, upper_shadow, i, is_high, p, dates[i])
        if s: signals.append(s)

        # 4. 放量大阴线 (Heavy Vol Big Bear)
        s = detect_heavy_vol_bear(close, high, open_, low, vol_ratio, i, is_high, p, dates[i])
        if s: signals.append(s)

        # 5. 反弹缩量 (Bounce Shrink Vol)
        s = detect_bounce_shrink_vol(close, volume, ema20, ema60, dates, i, in_downtrend, p)
        if s: signals.append(s)

        # ── 3 BUY signals ──

        # 1. 缩量止跌 (Shrinking Vol Stabilizes)
        s = detect_shrink_stabilize(close, volume, ema20, i, is_low, p, dates[i])
        if s: signals.append(s)

        # 2. 放量突破 (Volume Breakout)
        s = detect_volume_breakout(close, volume, ema20, i, p, dates[i])
        if s: signals.append(s)

        # 3. 低位地量 (Low Price Dry Volume)
        s = detect_low_dry_volume(close, volume, i, is_low, p, dates[i])
        if s: signals.append(s)

    return ScanResult(code=code, name=name, market=market, signals=signals)


# ═══════════════════════════════════════════════════════════════
# Sell signal detectors
# ═══════════════════════════════════════════════════════════════

def detect_high_vol_flat(close, vol_ratio, i, is_high, p, date) -> Signal | None:
    """放量滞涨: High volume but price flat at high position."""
    if not is_high:
        return None
    if vol_ratio[i] < p["volume_surge_ratio"]:
        return None
    change = abs(close[i] / close[i - 1] - 1) * 100
    if change > 0.5:
        return None
    return Signal(
        date=date, signal_type=SignalType.SELL, price=close[i],
        name="放量滞涨", risk_level=RiskLevel.HIGH, confidence=0.75,
        description=f"高位放量（量比{vol_ratio[i]:.1f}x）但价格未涨（涨幅{change:.2f}%）",
        metadata={"vol_ratio": vol_ratio[i], "price_change_pct": change},
    )


def detect_shrink_new_high(close, volume, dates, i, p) -> Signal | None:
    """缩量新高: New high with shrinking volume."""
    lookback = p["new_high_lookback"]
    if i < lookback:
        return None
    prev_high = max(close[i - lookback:i])
    if close[i] <= prev_high:
        return None
    vol_peak = max(volume[i - lookback:i])
    if volume[i] >= vol_peak * p["shrink_new_high_vol_pct"]:
        return None
    return Signal(
        date=dates[i], signal_type=SignalType.SELL, price=close[i],
        name="缩量新高", risk_level=RiskLevel.HIGH, confidence=0.78,
        description=f"创{lookback}日新高但量能缩至前高{volume[i] / vol_peak * 100:.0f}%",
        metadata={"prev_high": prev_high, "vol_peak_ratio": volume[i] / vol_peak},
    )


def detect_high_long_upper_shadow(close, high, open_, vol_ratio, upper_shadow, i, is_high, p, date) -> Signal | None:
    """高位长上影: Long upper shadow at high position."""
    if not is_high:
        return None
    if upper_shadow[i] < p["upper_shadow_ratio"]:
        return None
    body = abs(close[i] - open_[i])
    amplitude = high[i] - close[i]
    if close[i] >= open_[i]:
        return None  # green candle, less concerning
    if amplitude < (high[i] - low[i]) * 0.5:
        return None
    if vol_ratio[i] < 0.8:
        return None
    return Signal(
        date=date, signal_type=SignalType.SELL, price=close[i],
        name="高位长上影", risk_level=RiskLevel.HIGH, confidence=0.82,
        description=f"上影线/实体={upper_shadow[i]:.1f}x，冲高回落严重",
        metadata={"shadow_ratio": upper_shadow[i], "vol_ratio": vol_ratio[i]},
    )


def detect_heavy_vol_bear(close, high, open_, low, vol_ratio, i, is_high, p, date) -> Signal | None:
    """放量大阴线: Heavy volume bearish candle at high position."""
    if not is_high:
        return None
    if vol_ratio[i] < 1.5:
        return None
    change = (close[i] / close[i - 1] - 1) * 100
    if change > -p["bear_candle_pct"]:
        return None
    body = abs(close[i] - open_[i])
    amplitude = high[i] - low[i]
    if body < amplitude * 0.5:
        return None
    return Signal(
        date=date, signal_type=SignalType.SELL, price=close[i],
        name="放量大阴线", risk_level=RiskLevel.CRITICAL, confidence=0.88,
        description=f"放量{vol_ratio[i]:.1f}x跌{abs(change):.2f}%，大资金出逃信号",
        metadata={"vol_ratio": vol_ratio[i], "change_pct": change},
    )


def detect_bounce_shrink_vol(close, volume, ema20, ema60, dates, i, in_downtrend, p) -> Signal | None:
    """反弹缩量: Weak bounce with low volume in downtrend."""
    if not in_downtrend:
        return None
    if close[i] <= close[i - 1]:
        return None
    if vol_ratio := volume[i] / np.mean(volume[max(0, i - 20):i]):
        if vol_ratio > 1.0:
            return None
    decline_start = i - 10
    if decline_start < 10:
        return None
    decline_vol_mean = np.mean(volume[max(0, decline_start):i])
    if volume[i] > decline_vol_mean * p["bounce_shrink_vol_pct"]:
        return None
    bounce_amp = close[i] / close[i - 1] - 1
    prior_decline = close[i - 1] / close[max(0, decline_start)] - 1
    if bounce_amp > abs(prior_decline) * 0.5:
        return None
    return Signal(
        date=dates[i], signal_type=SignalType.SELL, price=close[i],
        name="反弹缩量", risk_level=RiskLevel.MEDIUM, confidence=0.72,
        description="下跌趋势中缩量反弹，弱反弹不是反转",
        metadata={"vol_ratio": volume[i] / decline_vol_mean if decline_vol_mean else 0},
    )


# ═══════════════════════════════════════════════════════════════
# Buy signal detectors
# ═══════════════════════════════════════════════════════════════

def detect_shrink_stabilize(close, volume, ema20, i, is_low, p, date) -> Signal | None:
    """缩量止跌: Volume dries up after decline at low price."""
    if not is_low:
        return None
    if close[i] < close[i - 1]:
        return None
    vol_ratio = volume[i] / np.mean(volume[max(0, i - 20):i])
    if vol_ratio > p["volume_dry_up_ratio"]:
        return None
    # Check prior decline
    prior_low = min(close[max(0, i - 20):i])
    if close[i] > prior_low * 1.03:
        return None
    return Signal(
        date=date, signal_type=SignalType.BUY, price=close[i],
        name="缩量止跌", risk_level=RiskLevel.LOW, confidence=0.70,
        description="低位缩量止跌企稳，卖压枯竭信号",
    )


def detect_volume_breakout(close, volume, ema20, i, p, date) -> Signal | None:
    """放量突破: Volume-driven breakout above MA20 with new high."""
    if close[i] < ema20[i]:
        return None
    lookback = 30
    if i < lookback:
        return None
    if close[i] < max(close[i - lookback:i]):
        return None
    vol_ratio = volume[i] / np.mean(volume[max(0, i - 20):i])
    if vol_ratio < p["breakout_volume_ratio"]:
        return None
    return Signal(
        date=date, signal_type=SignalType.BUY, price=close[i],
        name="放量突破", risk_level=RiskLevel.LOW, confidence=0.75,
        description=f"放量突破均线和前期高点，量比{vol_ratio:.1f}x",
        metadata={"vol_ratio": vol_ratio},
    )


def detect_low_dry_volume(close, volume, i, is_low, p, date) -> Signal | None:
    """低位地量: Extreme low volume at low price."""
    if not is_low:
        return None
    vol_20_mean = np.mean(volume[max(0, i - 20):i])
    if volume[i] > vol_20_mean * p["volume_dry_up_ratio"]:
        return None
    vol_60_mean = np.mean(volume[max(0, i - 60):i])
    if volume[i] > vol_60_mean * 0.4:
        return None
    return Signal(
        date=date, signal_type=SignalType.BUY, price=close[i],
        name="低位地量", risk_level=RiskLevel.LOW, confidence=0.68,
        description="地量见地价，成交量极度萎缩可能是底部区域",
    )


# ═══════════════════════════════════════════════════════════════
# Indicator helpers
# ═══════════════════════════════════════════════════════════════

def is_price_high(close, i, pct=0.70) -> bool:
    lookback = min(i, 120)
    return sum(1 for j in range(i - lookback, i + 1) if close[j] <= close[i]) / (lookback + 1) >= pct

def _is_price_low(close, i, pct=0.30) -> bool:
    lookback = min(i, 120)
    return sum(1 for j in range(i - lookback, i + 1) if close[j] >= close[i]) / (lookback + 1) >= (1 - pct)

def _volume_ratio(volume, period=20) -> np.ndarray:
    """Volume / 20-day average volume."""
    ma = _sma(volume, period)
    return np.divide(volume, ma, out=np.ones_like(volume), where=ma != 0)

def _upper_shadow_ratio(high, open_, close) -> np.ndarray:
    body = np.abs(np.subtract(close, open_))
    shadow = np.subtract(high, np.maximum(open_, close))
    return np.divide(shadow, body, out=np.zeros_like(shadow), where=body != 0)

def _is_downtrend(ema20, ema60, i) -> bool:
    return ema20[i] < ema60[i] and (i < 5 or ema20[i] < ema20[i - 5])

def _sma(arr, period) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=np.float64)
    if len(arr) >= period:
        cumsum = np.cumsum(np.insert(arr, 0, 0))
        result[period - 1:] = (cumsum[period:] - cumsum[:-period]) / period
    return result

def _ema(arr, period) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=np.float64)
    if len(arr) < period:
        return result
    result[period - 1] = np.mean(arr[:period])
    mult = 2.0 / (period + 1)
    for i in range(period, len(arr)):
        result[i] = (arr[i] - result[i - 1]) * mult + result[i - 1]
    return result
