"""Capital flow factors — main force flow, northbound, volume-price match."""

from __future__ import annotations

from typing import Any

from mystrategy.factors.base import BaseFactor, FactorMeta


class CapitalFlowFactors(BaseFactor):
    """Compute capital flow factor scores."""

    meta = FactorMeta(
        name="capital_flow_factors",
        category="capital_flow",
        display_name="资金面因子",
        description="Main force flow, northbound capital, volume-price correlation",
    )

    def compute(self, data: dict[str, Any]) -> dict[str, float]:
        """
        Args:
            data: should contain:
                - 'fund_flow': dict with daily fund flow data
                - 'northbound_flow': dict with northbound flow data (optional)
                - 'kline': DataFrame with OHLCV for volume-price analysis
        """
        fund_flow = data.get("fund_flow", {})
        scores: dict[str, float] = {}

        # 5-day main force net inflow
        daily = fund_flow.get("daily", [])
        if daily:
            main_5d = sum(d.get("main_net", 0) for d in daily[-5:])
            scores["main_flow_5d"] = self._linear_score(main_5d / 1e8, -1, 3)

            main_20d = sum(d.get("main_net", 0) for d in daily[-20:])
            scores["main_flow_20d"] = self._linear_score(main_20d / 1e8, -3, 8)

            # Big order ratio
            big_total = sum(abs(d.get("super_large_net", 0)) + abs(d.get("large_net", 0))
                          for d in daily[-5:])
            all_total = sum(abs(d.get("super_large_net", 0)) + abs(d.get("large_net", 0)) +
                          abs(d.get("medium_net", 0)) + abs(d.get("small_net", 0))
                          for d in daily[-5:])
            scores["big_order_ratio"] = big_total / all_total if all_total > 0 else 0.5
        else:
            scores["main_flow_5d"] = 0.5
            scores["main_flow_20d"] = 0.5
            scores["big_order_ratio"] = 0.5

        # Volume-price correlation
        kdf = data.get("kline")
        if kdf is not None and not kdf.empty:
            recent = kdf.tail(20)
            price_changes = recent["close"].pct_change().dropna().values
            vol_changes = recent["volume"].pct_change().dropna().values
            if len(price_changes) > 1:
                corr = sum((p - price_changes.mean()) * (v - vol_changes.mean())
                          for p, v in zip(price_changes, vol_changes))
                denom = (sum((p - price_changes.mean()) ** 2 for p in price_changes) *
                         sum((v - vol_changes.mean()) ** 2 for v in vol_changes)) ** 0.5
                vp_corr = corr / denom if denom > 0 else 0
                scores["volume_price_match"] = self._linear_score(vp_corr, -1, 1)
            else:
                scores["volume_price_match"] = 0.5
        else:
            scores["volume_price_match"] = 0.5

        # Northbound flow
        nb = data.get("northbound_flow", {})
        scores["north_flow"] = self._linear_score(nb.get("net", 0) / 1e9, -5, 10)

        # Weighted composite
        from mystrategy.config import CAPITAL_FLOW_SUB_WEIGHTS
        composite = 0.0
        for key, weight in CAPITAL_FLOW_SUB_WEIGHTS.items():
            composite += scores.get(key, 0.5) * weight
        scores["capital_flow_score"] = composite

        return scores

    def _linear_score(self, value: float, min_val: float, max_val: float) -> float:
        return max(0.0, min(1.0, (value - min_val) / (max_val - min_val + 1e-9)))
