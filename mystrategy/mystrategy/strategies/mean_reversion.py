"""Mean reversion + Donchian breakout strategies."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from mystrategy.strategies.base import (
    BaseStrategy, TradeSignal, SignalType, register_strategy,
)


def _sma(arr, period):
    result = np.full_like(arr, np.nan, dtype=np.float64)
    if len(arr) >= period:
        cumsum = np.cumsum(np.insert(arr, 0, 0))
        result[period - 1:] = (cumsum[period:] - cumsum[:-period]) / period
    return result


def _rolling_std(arr, period):
    result = np.full_like(arr, np.nan, dtype=np.float64)
    for i in range(period - 1, len(arr)):
        result[i] = np.std(arr[i - period + 1:i + 1], ddof=0)
    return result


@register_strategy("mean_reversion")
class MeanReversionStrategy(BaseStrategy):
    """Multi-condition mean reversion (Bollinger + Z-score + RSI + volume).

    Buy: Price < Lower Bollinger AND Z-score < -2 AND RSI < 35
    Sell: Price returns to MA20
    """

    name = "mean_reversion"
    description = "多条件均值回归（Bollinger + Z-score + RSI）"
    market = "A"

    def generate_signals(self) -> list[TradeSignal]:
        df: pd.DataFrame = self.data["kline"]
        close = df["close"].values.astype(np.float64)
        dates = df["date"].values

        period = self.params.get("bollinger_period", 20)
        std_mult = self.params.get("bollinger_std", 2)

        ma = _sma(close, period)
        std = _rolling_std(close, period)
        bb_lower = ma - std_mult * std

        # Z-score
        z_score = np.full_like(close, np.nan)
        for i in range(period, len(close)):
            seg = close[i - period:i]
            z_score[i] = (close[i] - np.mean(seg)) / np.std(seg) if np.std(seg) > 0 else 0

        # RSI
        rsi = _rsi(close, 14)

        signals = []
        in_position = False

        for i in range(period + 1, len(close)):
            if np.isnan(bb_lower[i]) or np.isnan(z_score[i]) or np.isnan(rsi[i]):
                continue

            # Buy condition
            oversold = close[i] < bb_lower[i] and z_score[i] < -2 and rsi[i] < 35
            if oversold and not in_position:
                signals.append(TradeSignal(
                    date=str(dates[i]), signal_type=SignalType.BUY, price=close[i],
                    reason=f"超跌反弹：价格{close[i]:.2f}<BB下轨{bb_lower[i]:.2f} Z={z_score[i]:.2f} RSI={rsi[i]:.1f}",
                    confidence=0.7,
                ))
                in_position = True

            # Sell: recovered to MA20
            elif in_position and close[i] >= ma[i]:
                signals.append(TradeSignal(
                    date=str(dates[i]), signal_type=SignalType.SELL, price=close[i],
                    reason=f"回归均线：回到MA20 {ma[i]:.2f}", confidence=0.65,
                ))
                in_position = False

            # Stop loss: break BB lower further
            elif in_position and close[i] < bb_lower[i] * 0.97:
                signals.append(TradeSignal(
                    date=str(dates[i]), signal_type=SignalType.SELL, price=close[i],
                    reason="止损：继续跌破下轨", confidence=0.8,
                ))
                in_position = False

        return signals


@register_strategy("donchian_breakout")
class DonchianBreakoutStrategy(BaseStrategy):
    """Turtle trading simplified (Donchian channel + ATR stop).

    Buy: Price breaks above 20-day high
    Sell: Price breaks below 10-day low (exit)
    """

    name = "donchian_breakout"
    description = "海龟交易简化版（Donchian通道 + ATR止损）"
    market = "A"

    def generate_signals(self) -> list[TradeSignal]:
        df: pd.DataFrame = self.data["kline"]
        close = df["close"].values.astype(np.float64)
        high = df["high"].values.astype(np.float64)
        low = df["low"].values.astype(np.float64)
        dates = df["date"].values

        entry_period = self.params.get("entry_period", 20)
        exit_period = self.params.get("exit_period", 10)

        n = len(close)
        dc_high = np.full(n, np.nan)
        dc_low = np.full(n, np.nan)
        exit_low = np.full(n, np.nan)

        for i in range(entry_period, n):
            dc_high[i] = max(high[i - entry_period:i])
            dc_low[i] = min(low[i - entry_period:i])

        for i in range(exit_period, n):
            exit_low[i] = min(low[i - exit_period:i])

        signals = []
        in_position = False

        for i in range(entry_period + 1, n):
            if np.isnan(dc_high[i]):
                continue

            # Breakout entry
            if close[i] > dc_high[i - 1] and not in_position:
                signals.append(TradeSignal(
                    date=str(dates[i]), signal_type=SignalType.BUY, price=close[i],
                    reason=f"突破{entry_period}日高点入场", confidence=0.65,
                ))
                in_position = True

            # Exit: break below exit channel
            elif in_position and close[i] < exit_low[i]:
                signals.append(TradeSignal(
                    date=str(dates[i]), signal_type=SignalType.SELL, price=close[i],
                    reason=f"跌破{exit_period}日低点出场", confidence=0.7,
                ))
                in_position = False

        return signals


def _rsi(close, period=14):
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = _ema(gain, period)
    avg_loss = _ema(loss, period)
    rs = np.divide(avg_gain, avg_loss, out=np.full_like(avg_gain, np.nan), where=avg_loss != 0)
    return 100.0 - (100.0 / (1.0 + rs))


def _ema(arr, period):
    result = np.full_like(arr, np.nan, dtype=np.float64)
    if len(arr) < period:
        return result
    result[period - 1] = np.mean(arr[:period])
    mult = 2.0 / (period + 1)
    for i in range(period, len(arr)):
        result[i] = (arr[i] - result[i - 1]) * mult + result[i - 1]
    return result
