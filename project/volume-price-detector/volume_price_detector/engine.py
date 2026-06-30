"""量价关系信号检测引擎。

核心：基于「背个竹筐」《一站式详解量价关系》第5集教学体系的五卖点信号。

用法:
    from volume_price_detector.engine import scan_stock

    result = scan_stock(df)  # df 是单只股票的 OHLCV DataFrame
    for s in result.signals:
        print(s)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from volume_price_detector.indicators import (
    ema,
    is_downtrend,
    is_price_high,
    rolling_max,
    sma,
    upper_shadow_ratio,
    volume_ratio,
)
from volume_price_detector.models import (
    RiskLevel,
    ScanResult,
    Signal,
    SignalType,
)

if TYPE_CHECKING:
    import pandas as pd


# ═══════════════════════════════════════════════════════════════
#  默认参数
# ═══════════════════════════════════════════════════════════════

DEFAULT_PARAMS = {
    "volume_surge_ratio": 1.5,      # 放量：量比 > 此值
    "high_position_pct": 0.70,      # 高位分位数阈值
    "new_high_lookback": 60,        # 缩量新高：回看天数
    "shrink_new_high_vol_pct": 0.7, # 缩量新高：当前量 < 前峰量 × 此值
    "bear_candle_pct": 3.0,         # 放量大阴线：最小跌幅(%)
    "upper_shadow_ratio": 2.0,      # 高位长上影：上影/实体 > 此值
    "bounce_shrink_vol_pct": 0.7,   # 反弹缩量：反弹量 < 前段均量 × 此值
}


# ═══════════════════════════════════════════════════════════════
#  顶层扫描入口
# ═══════════════════════════════════════════════════════════════

def scan_stock(
    df: pd.DataFrame,
    params: dict | None = None,
    name: str = "",
    market: str = "A",
) -> ScanResult:
    """扫描单只股票的五卖点信号。

    Args:
        df: 单只股票的 OHLCV DataFrame，列: [date, open, high, low, close, volume]
        params: 参数字典，覆盖默认值
        name: 股票名称
        market: 市场

    Returns:
        ScanResult 包含所有检测到的信号
    """
    p = {**DEFAULT_PARAMS, **(params or {})}

    if df.empty or len(df) < 60:
        return ScanResult(
            code=str(df["code"].iloc[0]) if "code" in df.columns else "?",
            name=name,
            market=market,
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

    # ── 预计算指标 ──
    vol_ratio_arr = volume_ratio(volume, 20)
    ma20 = ema(close, 20)
    ma60 = ema(close, 60)
    upper_shadow = upper_shadow_ratio(high, open_, close)

    # ── 逐日扫描 ──
    min_bars = 120
    start_idx = max(min_bars, 60)

    all_signals: list[Signal] = []

    for i in range(start_idx, n):
        dt = str(dates[i])[:10]

        if np.isnan(vol_ratio_arr[i]):
            continue

        sell_signals = _detect_sell_signals(
            i, close, high, low, open_, volume, dates, vol_ratio_arr,
            upper_shadow, p,
        )
        all_signals.extend(sell_signals)

    # ── 趋势和位置判断 ──
    last_idx = n - 1
    if ma20[last_idx] > ma60[last_idx]:
        trend = "uptrend"
    elif ma20[last_idx] < ma60[last_idx]:
        trend = "downtrend"
    else:
        trend = "rangebound"

    if is_price_high(close, last_idx, 120, p["high_position_pct"]):
        position = "high"
    else:
        position = "mid"

    return ScanResult(
        code=code,
        name=name,
        market=market,
        latest_price=float(close[-1]),
        latest_date=str(dates[-1])[:10],
        trend=trend,
        position=position,
        signals=all_signals,
    )


# ═══════════════════════════════════════════════════════════════
#  视频五卖点检测
# ═══════════════════════════════════════════════════════════════

def _detect_sell_signals(
    i: int,
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    open_: np.ndarray,
    volume: np.ndarray,
    dates: np.ndarray,
    vol_ratio_arr: np.ndarray,
    upper_shadow: np.ndarray,
    p: dict,
) -> list[Signal]:
    """检测「背个竹筐」第5集五卖点信号。"""
    results: list[Signal] = []
    dt = str(dates[i])[:10]

    is_high = is_price_high(close, i, 120, p["high_position_pct"])
    is_dn = is_downtrend(close, i)

    vol_surge = vol_ratio_arr[i] > p["volume_surge_ratio"]
    price_up = close[i] > close[i - 1] if i >= 1 else False
    price_down = close[i] < close[i - 1] if i >= 1 else False
    price_flat = (
        abs(close[i] / max(close[i - 1], 1e-8) - 1) < 0.005
        if i >= 1 else False
    )

    # ── 信号 1: 放量滞涨 ──
    sig1 = _high_vol_flat(close, i, is_high, vol_surge, price_flat, vol_ratio_arr, dt)
    if sig1: results.append(sig1)

    # ── 信号 2: 缩量新高 ──
    sig2 = _shrinking_vol_new_high(close, volume, i, is_high, vol_ratio_arr, p, dt)
    if sig2: results.append(sig2)

    # ── 信号 3: 高位长上影 ──
    sig3 = _high_long_upper_shadow(close, high, low, i, is_high, upper_shadow, vol_ratio_arr, p, dt)
    if sig3: results.append(sig3)

    # ── 信号 4: 放量大阴线 ──
    sig4 = _heavy_vol_big_bear(close, high, low, open_, i, is_high, vol_surge, price_down, vol_ratio_arr, p, dt)
    if sig4: results.append(sig4)

    # ── 信号 5: 反弹缩量 ──
    sig5 = _bounce_shrink_vol(close, volume, i, is_dn, price_up, vol_ratio_arr, p, dt)
    if sig5: results.append(sig5)

    return results


# ═══════════════════════════════════════════════════════════════
#  视频五信号实现
# ═══════════════════════════════════════════════════════════════

def _high_vol_flat(
    close: np.ndarray, i: int,
    is_high: bool, vol_surge: bool, price_flat: bool,
    vol_ratio_arr: np.ndarray, dt: str,
) -> Signal | None:
    """信号 1: 放量滞涨 — 量增价平，疑似对倒出货。

    视频原文: "价格高位但涨不动，成交量突然放大，说明卖的人更多，是典型的出货位。"
    """
    if not (is_high and vol_surge and price_flat):
        return None
    return Signal(
        date=dt,
        signal_type=SignalType.SELL,
        price=float(close[i]),
        name="放量滞涨",
        description=(
            f"放量 {vol_ratio_arr[i]:.1f} 倍但价格横盘 ¥{close[i]:.2f}，"
            "卖的人更多，典型出货位"
        ),
        risk_level=RiskLevel.HIGH,
        confidence=0.75,
        metadata={"vol_ratio": float(vol_ratio_arr[i])},
    )


def _shrinking_vol_new_high(
    close: np.ndarray, volume: np.ndarray, i: int,
    is_high: bool, vol_ratio_arr: np.ndarray,
    p: dict, dt: str,
) -> Signal | None:
    """信号 2: 缩量新高 — 股价创新高但成交量缩小，上涨动能减弱。

    视频原文: "股价创新高但成交量缩小，说明上涨动能减弱，可能是量价背离。"
    """
    lookback = p["new_high_lookback"]
    if i < lookback or not is_high:
        return None
    if np.isnan(vol_ratio_arr[i]):
        return None

    # 确认是 N 日新高
    if close[i] < rolling_max(close, lookback)[i] * 0.99:
        return None

    # 当前成交量相比前一个高点明显缩小
    peak_idx = i - lookback + int(np.argmax(close[i - lookback + 1 : i + 1]))
    if peak_idx >= i - 3:
        return None  # 前高太近，不是有效的"上一次高点"

    # 前高附近的成交量
    vol_start = max(0, peak_idx - 3)
    vol_end = min(len(volume) - 1, peak_idx + 4)
    vol_near_old_peak = float(np.max(volume[vol_start:vol_end]))

    # 当前成交量
    vol_current = float(np.max(volume[max(0, i - 2):i + 1]))

    ratio = vol_current / max(vol_near_old_peak, 1)
    if ratio < p["shrink_new_high_vol_pct"]:
        return Signal(
            date=dt,
            signal_type=SignalType.SELL,
            price=float(close[i]),
            name="缩量新高",
            description=(
                f"股价创 {lookback} 日新高 ¥{close[i]:.2f}，但成交量缩至前峰"
                f"{ratio:.0%} ({vol_near_old_peak:.0f}→{vol_current:.0f})，"
                "上涨动能减弱，量价背离"
            ),
            risk_level=RiskLevel.HIGH,
            confidence=0.78,
            metadata={
                "old_peak_idx": int(peak_idx),
                "old_peak_price": float(close[peak_idx]),
                "old_peak_vol": vol_near_old_peak,
                "current_vol": vol_current,
                "vol_ratio_pct": round(ratio, 3),
            },
        )
    return None


def _high_long_upper_shadow(
    close: np.ndarray, high: np.ndarray, low: np.ndarray, i: int,
    is_high: bool, upper_shadow: np.ndarray,
    vol_ratio_arr: np.ndarray,
    p: dict, dt: str,
) -> Signal | None:
    """信号 3: 高位长上影 — 冲高失败，资金出货坚决。

    视频原文: "高位长上影线，说明冲高失败，资金卖的坚决，卖点信号强。"
    """
    if i < 5 or not is_high:
        return None
    if np.isnan(upper_shadow[i]):
        return None

    # 跳过实体过小的 K 线（十字星/一字板，上影线比例无意义）
    if close[i] <= 0:
        return None
    body_pct = abs(close[i] - close[i - 1]) / close[i] if i >= 1 else 0
    if body_pct < 0.002:  # 实体 < 0.2%，视为无实体十字星
        return None

    # 上影线 > 实体 × threshold
    if upper_shadow[i] <= p["upper_shadow_ratio"]:
        return None

    # 确认当天冲高回落（收盘离高点较远）
    price_range = max(high[i] - low[i], 1e-8)
    if (high[i] - close[i]) / price_range < 0.5:
        return None  # 回落幅度不够

    # 成交量不能太小（至少 > 10日均量 × 0.8）
    if vol_ratio_arr[i] < 0.8:
        return None

    return Signal(
        date=dt,
        signal_type=SignalType.SELL,
        price=float(close[i]),
        name="高位长上影",
        description=(
            f"高位 ¥{close[i]:.2f}，上影线/实体={upper_shadow[i]:.1f}倍，"
            f"冲高 {(high[i] - close[i]) / max(price_range, 1e-8) * 100:.0f}% 后回落，"
            "资金抛售坚决，强卖点信号"
        ),
        risk_level=RiskLevel.HIGH,
        confidence=0.82,
        metadata={
            "upper_shadow_ratio": round(float(upper_shadow[i]), 2),
            "high": float(high[i]),
            "close": float(close[i]),
            "decline_pct": round(float((high[i] - close[i]) / max(price_range, 1e-8)), 3),
        },
    )


def _heavy_vol_big_bear(
    close: np.ndarray, high: np.ndarray, low: np.ndarray, open_: np.ndarray, i: int,
    is_high: bool, vol_surge: bool, price_down: bool,
    vol_ratio_arr: np.ndarray,
    p: dict, dt: str,
) -> Signal | None:
    """信号 4: 放量大阴线 — 大阴线+放量，资金态度根本性转变。

    视频原文: "放量大阴线，说明资金态度转变，接盘无力，需警惕。"
    """
    if i < 1 or not is_high:
        return None
    if not (vol_surge and price_down):
        return None

    # 确认是大阴线（跌幅 > threshold %）
    pct_chg = (close[i] / max(close[i - 1], 1e-8) - 1) * 100
    if pct_chg > -p["bear_candle_pct"]:
        return None

    # 阴线实体占比（实体 / 振幅 > 50% 才算"大"阴线）
    amplitude = (high[i] - low[i]) / max(close[i - 1], 1e-8) * 100
    body = abs(close[i] - open_[i]) / max(close[i - 1], 1e-8) * 100
    if amplitude > 0 and body / amplitude < 0.5:
        return None

    return Signal(
        date=dt,
        signal_type=SignalType.SELL,
        price=float(close[i]),
        name="放量大阴线",
        description=(
            f"高位放量 {vol_ratio_arr[i]:.1f} 倍大跌 {abs(pct_chg):.1f}%，"
            f"大阴线实体 {body:.1f}%，资金态度转变，接盘无力"
        ),
        risk_level=RiskLevel.CRITICAL,
        confidence=0.88,
        metadata={
            "pct_chg": round(pct_chg, 2),
            "vol_ratio": round(float(vol_ratio_arr[i]), 2),
            "body_pct": round(body, 2),
        },
    )


def _bounce_shrink_vol(
    close: np.ndarray, volume: np.ndarray, i: int,
    is_dn: bool, price_up: bool,
    vol_ratio_arr: np.ndarray,
    p: dict, dt: str,
) -> Signal | None:
    """信号 5: 反弹缩量 — 反弹缩量说明买盘不积极，是技术性喘息。

    视频原文: "反弹缩量，说明抛压小但买盘不积极，可能是技术性喘口气，不是真反转。"
    """
    if i < 10 or not is_dn:
        return None
    if not price_up:
        return None

    # 反弹日量比 < 1.0（缩量反弹）
    if vol_ratio_arr[i] >= 1.0:
        return None

    # 确认前一段是放量下跌：前5-15日均量 > 当前反弹量
    prev_start = max(0, i - 15)
    prev_end = max(0, i - 2)
    if prev_end <= prev_start:
        return None
    prev_vol_mean = float(np.mean(volume[prev_start:prev_end]))
    if np.isnan(prev_vol_mean) or prev_vol_mean <= 0:
        return None

    bounce_ratio = volume[i] / prev_vol_mean
    if bounce_ratio > p["bounce_shrink_vol_pct"]:
        return None

    # 确认反弹幅度不大（< 前期跌幅的 50%，典型的弱反弹）
    if i < 20:
        return None
    pre_high = float(np.max(close[max(0, i - 20):max(0, i - 5) + 1]))
    pre_low = float(np.min(close[max(0, i - 20):max(0, i - 5) + 1]))
    decline = pre_high - pre_low
    if decline > 0:
        rebound_pct = (close[i] - pre_low) / decline
        if rebound_pct > 0.5:
            return None  # 反弹过强，不是弱反弹

    return Signal(
        date=dt,
        signal_type=SignalType.SELL,
        price=float(close[i]),
        name="反弹缩量",
        description=(
            f"下跌趋势中缩量反弹，量仅前段均量的 {bounce_ratio:.0%}，"
            "买盘不积极，技术性喘息而非真反转"
        ),
        risk_level=RiskLevel.MEDIUM,
        confidence=0.72,
        metadata={
            "bounce_vol_ratio": round(float(bounce_ratio), 3),
            "prev_vol_mean": round(float(prev_vol_mean), 0),
        },
    )
