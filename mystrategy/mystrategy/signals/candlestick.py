"""Candlestick pattern recognition.

Detects 15+ classic candlestick patterns from OHLCV data.
Patterns: Doji, Hammer, Hanging Man, Engulfing, Morning/Evening Star,
Three White Soldiers, Three Black Crows, etc.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def detect_patterns(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Detect all candlestick patterns in a DataFrame.

    Args:
        df: OHLCV DataFrame with columns [date, open, high, low, close, volume]

    Returns:
        list of dicts with {date, pattern, direction, confidence, description}
    """
    if df.empty or len(df) < 3:
        return []

    open_ = df["open"].values.astype(np.float64)
    high = df["high"].values.astype(np.float64)
    low = df["low"].values.astype(np.float64)
    close = df["close"].values.astype(np.float64)
    dates = df["date"].values if "date" in df.columns else range(len(df))

    patterns = []

    for i in range(2, len(df)):
        patterns.extend(_detect_single_bar(open_, high, low, close, i, dates[i]))
        patterns.extend(_detect_two_bar(open_, high, low, close, i, dates[i]))
        patterns.extend(_detect_three_bar(open_, high, low, close, i, dates[i]))

    return patterns


def _body(open_, close, i) -> float:
    return abs(close[i] - open_[i])

def _upper_shadow(high, open_, close, i) -> float:
    return high[i] - max(open_[i], close[i])

def _lower_shadow(high, open_, close, i) -> float:
    return min(open_[i], close[i]) - low[i]

def _amplitude(high, low, i) -> float:
    return high[i] - low[i]


def _detect_single_bar(open_, high, low, close, i, date) -> list[dict]:
    patterns = []
    o, h, l, c = open_[i], high[i], low[i], close[i]
    body_val = abs(c - o)
    amplitude = h - l
    if amplitude == 0:
        return patterns

    is_green = c > o
    is_red = c < o

    # Doji
    if body_val <= amplitude * 0.1:
        if _lower_shadow(high, open_, close, i) > body_val * 3 and \
           _upper_shadow(high, open_, close, i) < body_val:
            patterns.append({"date": date, "pattern": "Dragonfly Doji", "direction": "bullish",
                           "confidence": 0.65, "description": "蜻蜓十字星，底部反转信号"})
        elif _upper_shadow(high, open_, close, i) > body_val * 3 and \
             _lower_shadow(high, open_, close, i) < body_val:
            patterns.append({"date": date, "pattern": "Gravestone Doji", "direction": "bearish",
                           "confidence": 0.65, "description": "墓碑十字星，顶部反转信号"})
        else:
            patterns.append({"date": date, "pattern": "Doji", "direction": "neutral",
                           "confidence": 0.55, "description": "十字星，趋势可能反转"})
        return patterns

    # Hammer / Hanging Man
    lower_shadow = _lower_shadow(high, open_, close, i)
    upper_shadow = _upper_shadow(high, open_, close, i)
    if lower_shadow >= body_val * 2 and upper_shadow <= body_val * 0.3:
        if _is_at_low(close, i):
            patterns.append({"date": date, "pattern": "Hammer", "direction": "bullish",
                           "confidence": 0.70, "description": "锤子线，底部看涨"})
        elif _is_at_high(close, i):
            patterns.append({"date": date, "pattern": "Hanging Man", "direction": "bearish",
                           "confidence": 0.70, "description": "上吊线，顶部看跌"})

    # Inverted Hammer / Shooting Star
    if upper_shadow >= body_val * 2 and lower_shadow <= body_val * 0.3:
        if _is_at_low(close, i):
            patterns.append({"date": date, "pattern": "Inverted Hammer", "direction": "bullish",
                           "confidence": 0.65, "description": "倒锤子，底部反转试探"})
        elif _is_at_high(close, i):
            patterns.append({"date": date, "pattern": "Shooting Star", "direction": "bearish",
                           "confidence": 0.72, "description": "射击之星，冲高失败"})

    # Marubozu
    if body_val >= amplitude * 0.9:
        if is_green:
            patterns.append({"date": date, "pattern": "Bullish Marubozu", "direction": "bullish",
                           "confidence": 0.75, "description": "光头光脚大阳线，强烈看涨"})
        else:
            patterns.append({"date": date, "pattern": "Bearish Marubozu", "direction": "bearish",
                           "confidence": 0.75, "description": "光头光脚大阴线，强烈看跌"})

    return patterns


def _detect_two_bar(open_, high, low, close, i, date) -> list[dict]:
    patterns = []
    if i < 1:
        return patterns

    body1, body2 = _body(open_, close, i - 1), _body(open_, close, i)
    amp2 = _amplitude(high, low, i)

    # Bullish Engulfing
    if close[i] > open_[i] and close[i - 1] < open_[i - 1]:
        if open_[i] <= close[i - 1] and close[i] >= open_[i - 1]:
            patterns.append({"date": date, "pattern": "Bullish Engulfing", "direction": "bullish",
                           "confidence": 0.78, "description": "阳包阴，强烈的底部反转信号"})

    # Bearish Engulfing
    if close[i] < open_[i] and close[i - 1] > open_[i - 1]:
        if open_[i] >= close[i - 1] and close[i] <= open_[i - 1]:
            patterns.append({"date": date, "pattern": "Bearish Engulfing", "direction": "bearish",
                           "confidence": 0.78, "description": "阴包阳，强烈的顶部反转信号"})

    # Piercing Line
    if close[i] > open_[i] and close[i - 1] < open_[i - 1]:
        prev_close, prev_open = close[i - 1], open_[i - 1]
        if open_[i] <= prev_close and close[i] >= (prev_close + prev_open) / 2 and close[i] < prev_open:
            patterns.append({"date": date, "pattern": "Piercing Line", "direction": "bullish",
                           "confidence": 0.72, "description": "曙光初现，底部反转"})

    # Dark Cloud Cover
    if close[i] < open_[i] and close[i - 1] > open_[i - 1]:
        prev_close, prev_open = close[i - 1], open_[i - 1]
        if open_[i] >= prev_close and close[i] <= (prev_close + prev_open) / 2 and close[i] > prev_open:
            patterns.append({"date": date, "pattern": "Dark Cloud Cover", "direction": "bearish",
                           "confidence": 0.72, "description": "乌云盖顶，顶部反转"})

    # Gap Up / Down
    if i >= 2:
        gap_up = low[i] > high[i - 1]
        gap_down = high[i] < low[i - 1]
        if gap_up:
            patterns.append({"date": date, "pattern": "Gap Up", "direction": "bullish",
                           "confidence": 0.60, "description": "跳空高开"})
        if gap_down:
            patterns.append({"date": date, "pattern": "Gap Down", "direction": "bearish",
                           "confidence": 0.60, "description": "跳空低开"})

    return patterns


def _detect_three_bar(open_, high, low, close, i, date) -> list[dict]:
    patterns = []
    if i < 2:
        return patterns

    # Morning Star
    if close[i] > open_[i] and close[i - 2] < open_[i - 2]:
        body1 = _body(open_, close, i - 2)
        body2 = _body(open_, close, i - 1)
        body3 = _body(open_, close, i)
        if body2 <= body1 * 0.3 and close[i] >= (open_[i - 2] + close[i - 2]) / 2:
            patterns.append({"date": date, "pattern": "Morning Star", "direction": "bullish",
                           "confidence": 0.80, "description": "启明星，三线底部反转形态"})

    # Evening Star
    if close[i] < open_[i] and close[i - 2] > open_[i - 2]:
        body1 = _body(open_, close, i - 2)
        body2 = _body(open_, close, i - 1)
        body3 = _body(open_, close, i)
        if body2 <= body1 * 0.3 and close[i] <= (open_[i - 2] + close[i - 2]) / 2:
            patterns.append({"date": date, "pattern": "Evening Star", "direction": "bearish",
                           "confidence": 0.80, "description": "黄昏星，三线顶部反转形态"})

    # Three White Soldiers
    if all(close[i - j] > open_[i - j] for j in [0, 1, 2]):
        if close[i] > close[i - 1] > close[i - 2] and \
           open_[i] > open_[i - 1] > open_[i - 2]:
            patterns.append({"date": date, "pattern": "Three White Soldiers", "direction": "bullish",
                           "confidence": 0.82, "description": "红三兵，强趋势延续"})

    # Three Black Crows
    if all(close[i - j] < open_[i - j] for j in [0, 1, 2]):
        if close[i] < close[i - 1] < close[i - 2] and \
           open_[i] < open_[i - 1] < open_[i - 2]:
            patterns.append({"date": date, "pattern": "Three Black Crows", "direction": "bearish",
                           "confidence": 0.82, "description": "三只乌鸦，强下跌趋势"})

    return patterns


def _is_at_high(close, i, lookback=60) -> bool:
    if i < lookback:
        return False
    return close[i] >= max(close[i - lookback:i])

def _is_at_low(close, i, lookback=60) -> bool:
    if i < lookback:
        return False
    return close[i] <= min(close[i - lookback:i])
