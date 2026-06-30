"""Fundamental factors — PE/PB ranking, ROE, growth, quality, DuPont.

Sources: Tencent valuation snapshots, mootdx financials, Sina income statements.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from mystrategy.factors.base import BaseFactor, FactorMeta

logger = logging.getLogger(__name__)


class FundamentalFactors(BaseFactor):
    """Compute fundamental factor scores."""

    meta = FactorMeta(
        name="fundamental_factors",
        category="fundamental",
        display_name="基本面因子",
        description="PE/PB ranking, ROE, profit/revenue growth, debt, cashflow, DuPont",
    )

    def compute(self, data: dict[str, Any]) -> dict[str, float]:
        """
        Args:
            data: should contain:
                - 'quote': valuation dict (PE, PB, market_cap, etc.)
                - 'financials': financial data dict or DataFrame
                - 'peer_pe': list of peer PE values (optional)
                - 'peer_pb': list of peer PB values (optional)
        """
        quote = data.get("quote", {})
        financials = data.get("financials", {})

        scores: dict[str, float] = {}

        # PE ranking
        pe = quote.get("pe_ttm", 0)
        peer_pe = data.get("peer_pe", [15, 20, 25, 30, 40])
        scores["pe_rank"] = self._rank_score(pe, peer_pe, lower_is_better=True)

        # PB ranking
        pb = quote.get("pb", 0)
        peer_pb = data.get("peer_pb", [1.5, 2.0, 2.5, 3.5, 5])
        scores["pb_rank"] = self._rank_score(pb, peer_pb, lower_is_better=True)

        # ROE
        roe = financials.get("roe", quote.get("roe", 0))
        scores["roe"] = self._linear_score(roe, min_val=0, max_val=30)

        # Profit growth
        profit_growth = financials.get("profit_growth", financials.get("net_profit_growth", 0))
        scores["profit_growth"] = self._linear_score(profit_growth, min_val=-20, max_val=50)

        # Revenue growth
        revenue_growth = financials.get("revenue_growth", 0)
        scores["revenue_growth"] = self._linear_score(revenue_growth, min_val=-10, max_val=40)

        # Debt ratio
        debt_ratio = financials.get("debt_ratio", financials.get("asset_liability_ratio", 50))
        scores["debt_ratio"] = 1.0 - self._linear_score(debt_ratio, min_val=10, max_val=80)

        # Cashflow quality: OCF / Net Profit
        ocf = financials.get("operating_cash_flow", financials.get("ocf", 0))
        net_profit = financials.get("net_profit", financials.get("net_income", 1))
        cf_quality = ocf / net_profit if net_profit else 0
        scores["cashflow_quality"] = self._linear_score(cf_quality, min_val=0.3, max_val=1.5)

        # QoQ revenue growth
        scores["revenue_qoq"] = self._linear_score(
            financials.get("revenue_qoq", 0), min_val=-10, max_val=20
        )
        scores["profit_qoq"] = self._linear_score(
            financials.get("profit_qoq", 0), min_val=-20, max_val=30
        )

        # Margin trend
        margin = financials.get("net_margin", 0)
        margin_prev = financials.get("net_margin_prev", margin)
        margin_change = (margin - margin_prev) / abs(margin_prev) if margin_prev else 0
        scores["margin_trend"] = self._linear_score(margin_change, min_val=-0.3, max_val=0.3)

        # DuPont analysis
        scores["dupont"] = self._dupont_score(financials)

        # Weighted composite
        from mystrategy.config import FUNDAMENTAL_SUB_WEIGHTS
        composite = 0.0
        for key, weight in FUNDAMENTAL_SUB_WEIGHTS.items():
            composite += scores.get(key, 0.5) * weight
        scores["fundamental_score"] = composite

        return scores

    def _rank_score(self, value: float, peer_values: list[float],
                    lower_is_better: bool = False) -> float:
        """Score by percentile rank among peers."""
        if not peer_values or value <= 0:
            return 0.5
        sorted_vals = sorted(peer_values)
        rank = sum(1 for v in sorted_vals if v <= value)
        pct = rank / len(sorted_vals)
        return 1.0 - pct if lower_is_better else pct

    def _linear_score(self, value: float, min_val: float, max_val: float) -> float:
        """Linear score in [0, 1]."""
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val)))

    def _dupont_score(self, financials: dict) -> float:
        """DuPont ROE decomposition quality score."""
        roe = financials.get("roe", 0)
        net_margin = financials.get("net_margin", 0)
        asset_turnover = financials.get("asset_turnover", 0)
        equity_multiplier = financials.get("equity_multiplier", 1)

        # Prefer ROE driven by margins and turnover over leverage
        if equity_multiplier > 1 and roe > 0:
            operational_roe = net_margin * asset_turnover * 100
            leverage_contrib = roe - operational_roe
            # Higher operational contribution = better
            quality = operational_roe / roe if roe > 0 else 0
            return max(0.0, min(1.0, quality))

        return 0.5
