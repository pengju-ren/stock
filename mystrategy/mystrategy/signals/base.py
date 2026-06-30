"""Signal base types — discrete trading events.

A Signal is a discrete event detected from market data, distinct from factors
(which are continuous values used for scoring/ranking).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Any


class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class RiskLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class Signal:
    """A single trading signal."""
    date: str | datetime
    signal_type: SignalType
    price: float
    name: str
    description: str = ""
    risk_level: RiskLevel = RiskLevel.MEDIUM
    confidence: float = 0.5  # 0.0 - 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScanResult:
    """Result of scanning a stock for signals."""
    code: str
    name: str = ""
    market: str = "A"
    signals: list[Signal] = field(default_factory=list)

    @property
    def buy_signals(self) -> list[Signal]:
        return [s for s in self.signals if s.signal_type == SignalType.BUY]

    @property
    def sell_signals(self) -> list[Signal]:
        return [s for s in self.signals if s.signal_type == SignalType.SELL]

    @property
    def risk_verdict(self) -> str:
        critical = sum(1 for s in self.sell_signals if s.risk_level == RiskLevel.CRITICAL)
        high = sum(1 for s in self.sell_signals if s.risk_level == RiskLevel.HIGH)
        medium = sum(1 for s in self.sell_signals if s.risk_level == RiskLevel.MEDIUM)

        if critical >= 1:
            return "高危 — 明确的出货信号"
        elif high >= 2:
            return "较高风险 — 多个卖点共振"
        elif high >= 1:
            return "中等风险 — 注意后续走势"
        elif medium >= 3:
            return "观望 — 多个弱势卖点"
        return "无明显卖出信号"
