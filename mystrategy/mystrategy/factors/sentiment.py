"""Sentiment factors — dragon-tiger board, hot rank, IR Q&A, KOL sentiment."""

from __future__ import annotations

from typing import Any

from mystrategy.factors.base import BaseFactor, FactorMeta


class SentimentFactors(BaseFactor):
    """Sentiment / market mood factors."""

    meta = FactorMeta(
        name="sentiment_factors",
        category="sentiment",
        display_name="情绪因子",
        description="龙虎榜活跃度、人气排名、互动易活跃度",
    )

    def compute(self, data: dict[str, Any]) -> dict[str, float]:
        scores: dict[str, float] = {}

        # Dragon-tiger board activity
        lhb = data.get("dragon_tiger", [])
        if lhb:
            lhb_count = len(lhb)
            lhb_net = sum(item.get("buy_amount", 0) - item.get("sell_amount", 0)
                         for item in lhb)
            scores["lhb_activity"] = min(1.0, lhb_count / 10)
            scores["lhb_net_buy"] = self._linear_score(lhb_net / 1e8, -2, 5)
        else:
            scores["lhb_activity"] = 0.0
            scores["lhb_net_buy"] = 0.3

        # Hot rank position
        hot_rank = data.get("hot_rank_position", 999)
        scores["hot_rank"] = max(0.0, 1.0 - hot_rank / 100)

        # IRM Q&A activity
        irm = data.get("irm_qa", [])
        scores["irm_activity"] = min(1.0, len(irm) / 20)

        # Concept heat
        concept_heat = data.get("concept_heat", 0)
        scores["concept_heat"] = min(1.0, concept_heat / 100)

        return scores

    def _linear_score(self, value: float, min_val: float, max_val: float) -> float:
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val + 1e-9)))
