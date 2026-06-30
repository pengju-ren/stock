"""Momentum strategies: RSI+MACD combined, RSI divergence."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from mystrategy.strategies.base import (
    BaseStrategy, TradeSignal, SignalType, StrategyRegistry, register_strategy,
)


@register_strategy("rsi_macd")
class RSIMACDStrategy(BaseStrategy):
    """RSI + MACD combined momentum strategy.

    Buy: RSI < 30 (oversold) AND MACD histogram turns positive
    Sell: RSI > 70 (overbought) AND MACD histogram turns negative
    """

    name = "rsi_macd"
    description = "RSI + MACD 组合动量策略"
    market = "A"

    def generate_signals(self) -> list[TradeSignal]:
        df: pd.DataFrame = self.data["kline"]
        close = df["close"].values.astype(np.float64)
        dates = df["date"].values

        rsi_period = self.params.get("rsi_period", 14)
        macd_fast = self.params.get("macd_fast", 12)
        macd_slow = self.params.get("macd_slow", 26)
        macd_signal = self.params.get("macd_signal", 9)
        rsi_oversold = self.params.get("rsi_oversold", 30)
        rsi_overbought = self.params.get("rsi_overbought", 70)

        rsi = _rsi(close, rsi_period)
        macd_hist = _macd_histogram(close, macd_fast, macd_slow, macd_signal)

        signals = []
        for i in range(2, len(close)):
            hist = macd_hist[i]
            hist_prev = macd_hist[i - 1]

            # Buy: RSI oversold + MACD histogram turns up
            if not np.isnan(rsi[i]) and rsi[i] < rsi_oversold and hist_prev <= 0 and hist > 0:
                signals.append(TradeSignal(
                    date=str(dates[i]), signal_type=SignalType.BUY, price=close[i],
                    reason=f"RSI={rsi[i]:.1f} 超卖 + MACD金叉", confidence=0.7,
                ))

            # Sell: RSI overbought + MACD histogram turns down
            elif not np.isnan(rsi[i]) and rsi[i] > rsi_overbought and hist_prev >= 0 and hist < 0:
                signals.append(TradeSignal(
                    date=str(dates[i]), signal_type=SignalType.SELL, price=close[i],
                    reason=f"RSI={rsi[i]:.1f} 超买 + MACD死叉", confidence=0.7,
                ))

        return signals


@register_strategy("rsi_divergence")
class RSIDivergenceStrategy(BaseStrategy):
    """RSI divergence strategy.

    Bullish divergence: Price makes lower low, RSI makes higher low
    Bearish divergence: Price makes higher high, RSI makes lower high
    """

    name = "rsi_divergence"
    description = "RSI 顶底背离策略"
    market = "A"

    def generate_signals(self) -> list[TradeSignal]:
        df: pd.DataFrame = self.data["kline"]
        close = df["close"].values.astype(np.float64)
        dates = df["date"].values

        rsi = _rsi(close, self.params.get("rsi_period", 14))
        lookback = self.params.get("lookback", 20)

        signals = []
        for i in range(lookback + 5, len(close)):
            segment = slice(i - lookback, i + 1)
            c_seg = close[segment]
            r_seg = rsi[segment]

            # Find local minimums
            c_min_idx = np.argmin(c_seg) + (i - lookback)
            r_min_idx = np.argmin(r_seg) + (i - lookback)

            # Bullish divergence: price lower low but RSI higher low
            if c_min_idx > r_min_idx and close[c_min_idx] < close[c_min_idx - 10] and \
               not np.isnan(rsi[c_min_idx]):
                signals.append(TradeSignal(
                    date=str(dates[i]), signal_type=SignalType.BUY, price=close[i],
                    reason=f"RSI底背离：价格新低但RSI未新低", confidence=0.65,
                ))

            # Find local maximums
            c_max_idx = np.argmax(c_seg) + (i - lookback)
            r_max_idx = np.argmax(r_seg) + (i - lookback)

            # Bearish divergence
            if c_max_idx > r_max_idx and close[c_max_idx] > close[c_max_idx - 10] and \
               not np.isnan(rsi[c_max_idx]):
                signals.append(TradeSignal(
                    date=str(dates[i]), signal_type=SignalType.SELL, price=close[i],
                    reason=f"RSI顶背离：价格新高但RSI未新高", confidence=0.65,
                ))

        return signals


# ── Helpers ──

def _rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = _ema(gain, period)
    avg_loss = _ema(loss, period)
    rs = np.divide(avg_gain, avg_loss, out=np.full_like(avg_gain, np.nan), where=avg_loss != 0)
    return 100.0 - (100.0 / (1.0 + rs))


def _ema(arr: np.ndarray, period: int) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=np.float64)
    if len(arr) < period:
        return result
    result[period - 1] = np.mean(arr[:period])
    mult = 2.0 / (period + 1)
    for i in range(period, len(arr)):
        result[i] = (arr[i] - result[i - 1]) * mult + result[i - 1]
    return result


def _macd_histogram(close, fast=12, slow=26, signal=9) -> np.ndarray:
    ema_fast = _ema(close, fast)
    ema_slow = _ema(close, slow)
    dif = ema_fast - ema_slow
    dea = _ema(dif, signal)
    return 2 * (dif - dea)
