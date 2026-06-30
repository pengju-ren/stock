"""量价关系检测器 — 数据模型定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class SignalType(StrEnum):
    """信号类型。"""
    BUY = "buy"
    SELL = "sell"


class RiskLevel(StrEnum):
    """风险等级。"""
    CRITICAL = "critical"   # 必须立即处理
    HIGH = "high"           # 高度关注
    MEDIUM = "medium"       # 关注
    LOW = "low"             # 低风险


@dataclass
class Signal:
    """单条量价信号。

    Attributes:
        date: 信号日期 (YYYY-MM-DD)
        signal_type: 买入/卖出
        price: 当日收盘价
        name: 信号名称（如 "量价顶背离"）
        description: 信号详细描述
        risk_level: 风险等级（卖点）或 None（买点）
        confidence: 置信度 0.0~1.0
        metadata: 额外数据
    """

    date: str
    signal_type: SignalType
    price: float
    name: str
    description: str = ""
    risk_level: RiskLevel | None = None
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        emoji = "🔴" if self.signal_type == SignalType.SELL else "🟢"
        conf_bar = "█" * int(self.confidence * 10)
        return (
            f"{emoji} [{self.date}] {self.name} "
            f"@ ¥{self.price:.2f} "
            f"[{conf_bar:<10}] {self.confidence:.0%}"
        )


@dataclass
class ScanResult:
    """单只股票的扫描结果。

    Attributes:
        code: 股票代码
        name: 股票名称（可选）
        market: 市场 (A/HK/US/ETF)
        latest_price: 最新收盘价
        latest_date: 最新数据日期
        trend: 趋势判断 (uptrend/downtrend/rangebound)
        signals: 所有检测到的信号
    """

    code: str
    name: str = ""
    market: str = "A"
    latest_price: float = 0.0
    latest_date: str = ""
    trend: str = "unknown"
    position: str = "unknown"  # high / low / mid
    signals: list[Signal] = field(default_factory=list)

    @property
    def sell_signals(self) -> list[Signal]:
        return [s for s in self.signals if s.signal_type == SignalType.SELL]

    @property
    def buy_signals(self) -> list[Signal]:
        return [s for s in self.signals if s.signal_type == SignalType.BUY]

    def recent_signals(self, days: int = 20) -> list[Signal]:
        """最近 N 天的信号。"""
        if not self.signals or not self.latest_date:
            return self.signals
        from datetime import timedelta
        cutoff = datetime.strptime(self.latest_date, "%Y-%m-%d") - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")
        return [s for s in self.signals if s.date >= cutoff_str]

    @property
    def risk_summary(self) -> dict[str, int]:
        """风险信号汇总计数。"""
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for s in self.sell_signals:
            if s.risk_level:
                counts[s.risk_level.value] += 1
        return counts

    @property
    def risk_verdict(self) -> str:
        """综合风险判断。"""
        r = self.risk_summary
        if r["critical"] > 0:
            return "⚠️ 高风险 — 有明确出货信号，建议减仓或清仓"
        if r["high"] >= 2:
            return "🔶 较高风险 — 多个卖点共振，密切跟踪"
        if r["high"] >= 1:
            return "🔸 中等风险 — 有卖出信号，注意观察后续走势"
        if r["medium"] >= 3:
            return "🔹 关注 — 多个弱卖点出现"
        return "✅ 暂无显著卖出信号"
