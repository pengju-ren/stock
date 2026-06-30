"""Strategy registry — all registered strategies available.

Import strategy modules to auto-register them.
"""

from mystrategy.strategies.base import BaseStrategy, StrategyRegistry
from mystrategy.strategies import momentum  # RSI_MACD, RSI_Divergence
from mystrategy.strategies import trend     # TripleMA, MACrossover, SwingTrend
from mystrategy.strategies import mean_reversion  # MeanReversion, DonchianBreakout
from mystrategy.strategies import volume_price_strategy  # VolumePrice

__all__ = [
    "BaseStrategy", "StrategyRegistry",
]
