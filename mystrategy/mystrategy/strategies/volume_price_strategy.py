"""Volume-price relationship strategy (9 sell + 3 buy signals).

Based on the "背个竹筐" teaching system.
"""

from __future__ import annotations

from typing import Any

from mystrategy.strategies.base import (
    BaseStrategy, TradeSignal, SignalType, register_strategy,
)
from mystrategy.signals.volume_price import scan_stock, DEFAULT_PARAMS


@register_strategy("volume_price")
class VolumePriceStrategy(BaseStrategy):
    """Volume-price 9-sell + 3-buy signal strategy.

    Uses the volume-price signal detector to generate trading signals.
    """

    name = "volume_price"
    description = "量价关系策略（9卖+3买，背个竹筐体系）"
    market = "A"

    def generate_signals(self) -> list[TradeSignal]:
        df = self.data.get("kline")
        if df is None or df.empty:
            return []

        params = {**DEFAULT_PARAMS, **self.params}
        result = scan_stock(df, params=params)

        signals = []
        for sig in result.signals:
            st = SignalType.BUY if sig.signal_type.value == "BUY" else SignalType.SELL
            signals.append(TradeSignal(
                date=str(sig.date), signal_type=st, price=sig.price,
                reason=f"{sig.name}: {sig.description}", confidence=sig.confidence,
                metadata=sig.metadata,
            ))

        return signals
