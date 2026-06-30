"""Portfolio management — optimization, risk, rebalancing, tracking.

Key constraints (from ai-berkshire):
    - Max single position: 40%
    - Top 3 holdings: 50-80%
    - Total positions: 5-15
    - Cash: 10-30%
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PortfolioHolding:
    code: str
    name: str
    shares: int = 0
    avg_cost: float = 0.0
    current_price: float = 0.0
    thesis_health: int = 10
    expected_return: float = 0.0

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price

    @property
    def weight(self) -> float:
        return 0.0  # Set externally

    @property
    def pnl_pct(self) -> float:
        return (self.current_price / self.avg_cost - 1) if self.avg_cost else 0


@dataclass
class Portfolio:
    holdings: list[PortfolioHolding] = field(default_factory=list)
    cash: float = 1_000_000
    total_value: float = 0.0

    def analyze(self) -> dict[str, Any]:
        """Run portfolio analysis: concentration, opportunity cost, stress test."""
        total = self.cash + sum(h.market_value for h in self.holdings)
        self.total_value = total

        # Update weights
        for h in self.holdings:
            h.weight = h.market_value / total if total > 0 else 0

        # Concentration check
        sorted_holdings = sorted(self.holdings, key=lambda h: h.market_value, reverse=True)
        top1_weight = sorted_holdings[0].weight * 100 if sorted_holdings else 0
        top3_weight = sum(h.weight for h in sorted_holdings[:3]) * 100
        position_count = len(self.holdings)
        cash_pct = self.cash / total * 100

        # Risk flags
        flags = []
        if top1_weight > 40:
            flags.append(f"最大持仓{top1_weight:.1f}%超过40%上限")
        if top3_weight > 80:
            flags.append(f"前3持仓{top3_weight:.1f}%超过80%上限")
        if position_count < 5:
            flags.append(f"持仓数{position_count}少于5只")
        elif position_count > 15:
            flags.append(f"持仓数{position_count}超过15只上限")
        if cash_pct < 10:
            flags.append(f"现金比例{cash_pct:.1f}%低于10%最低线")
        elif cash_pct > 30:
            flags.append(f"现金比例{cash_pct:.1f}%超过30%上限")

        # Opportunity cost ranking
        ranked = sorted(self.holdings, key=lambda h: h.expected_return, reverse=True)
        lowest = ranked[-1] if ranked else None

        return {
            "total_value": total,
            "cash_pct": cash_pct,
            "position_count": position_count,
            "top1_weight": top1_weight,
            "top3_weight": top3_weight,
            "flags": flags,
            "lowest_expected_return": lowest.expected_return if lowest else 0,
            "holdings_weight": [(h.code, h.weight * 100, h.thesis_health) for h in sorted_holdings],
        }

    def optimize_weights(self, risk_free_rate: float = 0.04) -> dict[str, float]:
        """Simple equal-risk-contribution weight optimization.

        Returns dict[code] -> target_weight.
        """
        if not self.holdings:
            return {}

        n = len(self.holdings)
        # Equal weight as baseline
        base_weight = 1.0 / n

        weights = {}
        for h in self.holdings:
            # Adjust: higher thesis health → slightly higher weight
            health_adj = 0.8 + 0.2 * (h.thesis_health / 10)
            # Adjust: higher expected return → slightly higher weight
            return_adj = 0.9 + 0.1 * max(0, min(2, h.expected_return / risk_free_rate))
            weights[h.code] = base_weight * health_adj * return_adj

        # Normalize to sum to 1.0
        total_w = sum(weights.values())
        return {k: v / total_w for k, v in weights.items()}
