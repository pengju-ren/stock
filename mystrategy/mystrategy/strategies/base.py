"""Base strategy class and signal types.

Strategy lifecycle:
    init → pre_check → generate_signals → size_position → execute → post_trade
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@dataclass
class TradeSignal:
    """A single trade signal from a strategy."""
    date: str
    signal_type: SignalType
    price: float
    size: float = 0.0  # # of shares
    reason: str = ""
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    """Current position state."""
    code: str
    shares: int = 0
    avg_cost: float = 0.0
    current_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price

    @property
    def cost_basis(self) -> float:
        return self.shares * self.avg_cost

    @property
    def pnl(self) -> float:
        return self.market_value - self.cost_basis

    @property
    def pnl_pct(self) -> float:
        return (self.current_price / self.avg_cost - 1) if self.avg_cost else 0


class BaseStrategy(ABC):
    """Abstract base for all trading strategies.

    Subclasses must implement generate_signals().
    """

    name: str = "base"
    description: str = ""
    version: str = "1.0"
    market: str = "A"

    def __init__(self, params: dict[str, Any] | None = None):
        self.params = params or {}
        self.position = Position(code="", shares=0, avg_cost=0.0)
        self.signals: list[TradeSignal] = []
        self._initialized = False

    def init(self, data: dict[str, Any]):
        """Initialize strategy with market data."""
        self.data = data
        self._initialized = True

    def pre_check(self) -> bool:
        """Check if strategy can trade (e.g., market open, valid data)."""
        if not self._initialized:
            return False
        kline = self.data.get("kline")
        if kline is None or kline.empty:
            return False
        return True

    @abstractmethod
    def generate_signals(self) -> list[TradeSignal]:
        """Generate trading signals. Must be implemented by subclass."""
        ...

    def size_position(self, signal: TradeSignal, capital: float) -> float:
        """Calculate position size for a signal.

        Default: equal-weight allocation using 10% of capital.
        """
        return int(capital * 0.10 / signal.price / 100) * 100  # Round to lot

    def execute(self, signal: TradeSignal) -> dict:
        """Execute a trade signal (simulated)."""
        if signal.signal_type == SignalType.BUY:
            self.position.shares += int(signal.size)
            self.position.avg_cost = (
                (self.position.avg_cost * (self.position.shares - signal.size) + signal.price * signal.size)
                / self.position.shares if self.position.shares else signal.price
            )
        elif signal.signal_type == SignalType.SELL:
            self.position.shares = max(0, self.position.shares - int(signal.size))

        return {
            "action": signal.signal_type.value,
            "price": signal.price,
            "size": signal.size,
            "position": self.position.shares,
        }

    def run(self, data: dict[str, Any], capital: float = 1_000_000) -> list[dict]:
        """Full strategy execution pipeline."""
        self.init(data)

        if not self.pre_check():
            return []

        signals = self.generate_signals()
        trades = []

        for sig in signals:
            sig.size = self.size_position(sig, capital)
            trade = self.execute(sig)
            trade["reason"] = sig.reason
            trade["confidence"] = sig.confidence
            trades.append(trade)

        self.signals = signals
        return trades


class StrategyRegistry:
    """Registry for all available strategies."""

    _strategies: dict[str, type[BaseStrategy]] = {}

    @classmethod
    def register(cls, strategy_cls: type[BaseStrategy]):
        """Register a strategy class."""
        name = strategy_cls.name or strategy_cls.__name__.lower()
        cls._strategies[name] = strategy_cls
        return strategy_cls

    @classmethod
    def get(cls, name: str) -> type[BaseStrategy] | None:
        return cls._strategies.get(name)

    @classmethod
    def list_all(cls) -> list[str]:
        return list(cls._strategies.keys())

    @classmethod
    def create(cls, name: str, params: dict | None = None) -> BaseStrategy | None:
        strat_cls = cls.get(name)
        if strat_cls is None:
            return None
        return strat_cls(params)


# Decorator for easy registration
def register_strategy(name: str = ""):
    def decorator(cls):
        if name:
            cls.name = name
        StrategyRegistry.register(cls)
        return cls
    return decorator
