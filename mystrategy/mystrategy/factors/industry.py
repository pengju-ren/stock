"""Industry factors — rotation scoring, classification, momentum."""

from __future__ import annotations

from typing import Any

import numpy as np

from mystrategy.factors.base import BaseFactor, FactorMeta


class IndustryFactors(BaseFactor):
    """Industry rotation & classification factors."""

    meta = FactorMeta(
        name="industry_factors",
        category="industry",
        display_name="行业因子",
        description="行业轮动得分、板块动量、行业分类",
    )

    def compute(self, data: dict[str, Any]) -> dict[str, float]:
        """
        Args:
            data: should contain:
                - 'industry_comparison': list of peer stocks in same industry with scores
                - 'industry_name': industry classification
        """
        peers = data.get("industry_comparison", [])
        scores: dict[str, float] = {}

        if peers:
            # Industry average metrics
            pe_vals = [p.get("pe_ttm", 0) for p in peers if p.get("pe_ttm")]
            change_vals = [p.get("change_pct", 0) for p in peers]

            avg_change = np.mean(change_vals) if change_vals else 0
            scores["industry_momentum"] = self._linear_score(avg_change, -3, 5)

            scores["industry_pe_mean"] = np.mean(pe_vals) if pe_vals else 0
        else:
            scores["industry_momentum"] = 0.5
            scores["industry_pe_mean"] = 0

        # Industry rank
        rank = data.get("industry_rank", 50)
        scores["industry_rank_score"] = max(0.0, 1.0 - rank / 100)

        return scores

    def _linear_score(self, value: float, min_val: float, max_val: float) -> float:
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val + 1e-9)))
