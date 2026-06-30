"""Trend-following strategies: Triple MA, MA crossover."""

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


@register_strategy("triple_ma_trend")
class TripleMATrendStrategy(BaseStrategy):
    """Triple MA trend following (5/20/60) with turtle-style pyramiding.

    Buy: MA5 > MA20 > MA60 (bullish alignment) AND price > MA5
    Sell: Price < MA60 (trend broken)
    """

    name = "triple_ma_trend"
    description = "三重MA趋势跟踪（5/20/60）+ 海龟加仓"
    market = "A"

    def generate_signals(self) -> list[TradeSignal]:
        df: pd.DataFrame = self.data["kline"]
        close = df["close"].values.astype(np.float64)
        dates = df["date"].values

        ma_short = self.params.get("ma_short", 5)
        ma_medium = self.params.get("ma_medium", 20)
        ma_long = self.params.get("ma_long", 60)

        ma5 = _sma(close, ma_short)
        ma20 = _sma(close, ma_medium)
        ma60 = _sma(close, ma_long)

        signals = []
        in_position = False

        for i in range(ma_long + 1, len(close)):
            if np.isnan(ma60[i]):
                continue

            bullish = ma5[i] > ma20[i] > ma60[i] and close[i] > ma5[i]
            trend_broken = close[i] < ma60[i]

            if bullish and not in_position:
                signals.append(TradeSignal(
                    date=str(dates[i]), signal_type=SignalType.BUY, price=close[i],
                    reason=f"三重MA多头排列：MA5{ma5[i]:.2f} > MA20{ma20[i]:.2f} > MA60{ma60[i]:.2f}",
                    confidence=0.75,
                ))
                in_position = True

            elif trend_broken and in_position:
                signals.append(TradeSignal(
                    date=str(dates[i]), signal_type=SignalType.SELL, price=close[i],
                    reason=f"趋势破位：跌破MA60 {ma60[i]:.2f}", confidence=0.7,
                ))
                in_position = False

            # Pyramiding: add on pullback to MA20
            elif in_position and close[i - 1] < ma20[i - 1] and close[i] > ma20[i]:
                signals.append(TradeSignal(
                    date=str(dates[i]), signal_type=SignalType.BUY, price=close[i],
                    reason="海龟加仓：回踩MA20后拉升", confidence=0.6,
                ))

        return signals


@register_strategy("ma_crossover")
class MACrossoverStrategy(BaseStrategy):
    """Classic dual MA crossover strategy (5/20).

    Buy: MA5 crosses above MA20 (golden cross)
    Sell: MA5 crosses below MA20 (death cross)
    """

    name = "ma_crossover"
    description = "经典双均线交叉策略（5/20）"
    market = "A"

    def generate_signals(self) -> list[TradeSignal]:
        df: pd.DataFrame = self.data["kline"]
        close = df["close"].values.astype(np.float64)
        dates = df["date"].values

        ma_fast = self.params.get("ma_fast", 5)
        ma_slow = self.params.get("ma_slow", 20)

        fma = _sma(close, ma_fast)
        sma_ = _sma(close, ma_slow)

        signals = []
        for i in range(2, len(close)):
            if np.isnan(sma_[i]) or np.isnan(fma[i]):
                continue

            # Golden cross
            if fma[i - 1] <= sma_[i - 1] and fma[i] > sma_[i]:
                signals.append(TradeSignal(
                    date=str(dates[i]), signal_type=SignalType.BUY, price=close[i],
                    reason=f"金叉：MA{ma_fast}上穿MA{ma_slow}", confidence=0.65,
                ))

            # Death cross
            elif fma[i - 1] >= sma_[i - 1] and fma[i] < sma_[i]:
                signals.append(TradeSignal(
                    date=str(dates[i]), signal_type=SignalType.SELL, price=close[i],
                    reason=f"死叉：MA{ma_fast}下穿MA{ma_slow}", confidence=0.65,
                ))

        return signals


@register_strategy("swing_trend")
class SwingTrendStrategy(BaseStrategy):
    """Swing trend: weekly MA30 + daily MA5/30/60 multi-timeframe confirmation.

    Buy: Weekly MA30 rising + daily MA5 > MA30 > MA60 + price pullback to MA30
    Sell: Weekly MA30 turning down OR daily MA death cross below MA60
    """

    name = "swing_trend"
    description = "波段趋势（周线MA30 + 日线多周期）"
    market = "A"

    def generate_signals(self) -> list[TradeSignal]:
        df: pd.DataFrame = self.data.get("weekly_kline", self.data["kline"])
        daily = self.data.get("kline")

        if daily is None or daily.empty:
            return []

        close = daily["close"].values.astype(np.float64)
        dates = daily["date"].values

        ma5 = _sma(close, 5)
        ma30 = _sma(close, 30)
        ma60 = _sma(close, 60)

        signals = []
        in_position = False

        for i in range(60, len(close)):
            if np.isnan(ma60[i]):
                continue

            # Weekly MA30 rising (approximated by daily trend check)
            weekly_trend_up = ma30[i] > ma30[i - 5]  # MA30 rising over 5 days

            # Buy: weekly MA30 rising + daily MA5 > MA30 > MA60 + pullback
            daily_bullish = ma5[i] > ma30[i] > ma60[i]
            pullback = close[i] <= ma30[i] * 1.02  # Near or at MA30

            if weekly_trend_up and daily_bullish and pullback and not in_position:
                signals.append(TradeSignal(
                    date=str(dates[i]), signal_type=SignalType.BUY, price=close[i],
                    reason=f"波段买点：周线上升+日线多头+回踩MA30", confidence=0.72,
                ))
                in_position = True

            # Sell: trend broken
            elif in_position and (close[i] < ma60[i] or (not weekly_trend_up and close[i] < ma30[i])):
                signals.append(TradeSignal(
                    date=str(dates[i]), signal_type=SignalType.SELL, price=close[i],
                    reason="波段卖点：趋势破位或周线转弱", confidence=0.7,
                ))
                in_position = False

        return signals
