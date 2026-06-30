"""Valuation factors — PEG, PE digestion, DCF, Graham number, valuation bands."""

from __future__ import annotations

import math
from decimal import Decimal, getcontext
from typing import Any

from mystrategy.factors.base import BaseFactor, FactorMeta

getcontext().prec = 28


class ValuationFactors(BaseFactor):
    """Valuation factor calculations."""

    meta = FactorMeta(
        name="valuation_factors",
        category="valuation",
        display_name="估值因子",
    )

    def compute(self, data: dict[str, Any]) -> dict[str, float]:
        quote = data.get("quote", {})
        financials = data.get("financials", {})
        scores: dict[str, float] = {}

        # PEG calculation
        pe = quote.get("pe_ttm", 0)
        cagr = financials.get("cagr", financials.get("net_profit_cagr", 15)) / 100
        if pe > 0 and cagr > 0:
            peg = pe / (cagr * 100)
        else:
            peg = 999
        scores["peg"] = peg
        scores["peg_score"] = self._peg_to_score(peg)

        # PE digestion years
        if pe > 0 and cagr > 0:
            digestion = math.log(max(pe, 1) / 30) / math.log(1 + cagr) if pe > 30 else 0
        else:
            digestion = 999
        scores["digestion_years"] = max(0, digestion)
        scores["digestion_score"] = max(0.0, min(1.0, 1.0 - digestion / 20))

        # Graham Number
        eps = financials.get("eps", 0)
        bps = financials.get("bps", financials.get("book_per_share", 0))
        if eps > 0 and bps > 0:
            graham_value = math.sqrt(22.5 * eps * bps)
            price = quote.get("price", 0)
            graham_ratio = graham_value / price if price > 0 else 0
        else:
            graham_ratio = 0
        scores["graham_ratio"] = graham_ratio
        scores["graham_score"] = min(1.0, max(0.0, (graham_ratio - 0.5) / 1.5))

        # DCF-based fair value (simplified two-stage model)
        fcf = financials.get("fcf", financials.get("free_cash_flow", 0))
        growth = financials.get("fcf_growth", 10) / 100  # High growth rate
        terminal_growth = 0.03
        discount_rate = 0.10
        shares = financials.get("shares", quote.get("shares_outstanding", 1))
        if fcf > 0 and shares > 0:
            fcf_val = self._dcf_fair_value(fcf, growth, terminal_growth, discount_rate)
            fair_price = fcf_val / shares
            price = quote.get("price", 0)
            scores["dcf_fair_value"] = fair_price
            scores["dcf_upside"] = fair_price / price - 1 if price > 0 else 0
            scores["dcf_score"] = min(1.0, max(0.0, (fair_price / price - 0.7) / 0.6)) if price > 0 else 0.5
        else:
            scores["dcf_score"] = 0.3

        # PB Band position
        pb = quote.get("pb", 0)
        pb_low = financials.get("pb_5yr_low", pb * 0.6)
        pb_high = financials.get("pb_5yr_high", pb * 1.8)
        if pb_high != pb_low:
            pb_pct = (pb - pb_low) / (pb_high - pb_low)
        else:
            pb_pct = 0.5
        scores["pb_band_pct"] = pb_pct
        scores["pb_band_score"] = max(0.0, 1.0 - pb_pct)  # lower is cheaper

        # PE Band position
        pe = quote.get("pe_ttm", 0)
        pe_low = financials.get("pe_5yr_low", pe * 0.5)
        pe_high = financials.get("pe_5yr_high", pe * 2)
        if pe_high != pe_low:
            pe_pct = (pe - pe_low) / (pe_high - pe_low)
        else:
            pe_pct = 0.5
        scores["pe_band_pct"] = pe_pct
        scores["pe_band_score"] = max(0.0, 1.0 - pe_pct)

        return scores

    def _peg_to_score(self, peg: float) -> float:
        """PEG rating from Peter Lynch."""
        if peg < 0.5:
            return 0.95  # Extremely undervalued
        elif peg < 1.0:
            return 0.8   # Undervalued
        elif peg < 1.5:
            return 0.55  # Fair
        elif peg < 2.0:
            return 0.35  # Slightly expensive
        else:
            return 0.1   # Overvalued

    def _dcf_fair_value(self, fcf: float, growth: float,
                        terminal_growth: float, discount_rate: float) -> float:
        """Two-stage DCF model: 5yr high growth + terminal."""
        total = 0.0
        fcf_current = fcf
        for year in range(1, 6):
            fcf_current *= (1 + growth)
            total += fcf_current / (1 + discount_rate) ** year

        # Terminal value (Gordon Growth)
        terminal_fcf = fcf_current * (1 + terminal_growth)
        terminal_value = terminal_fcf / (discount_rate - terminal_growth)
        terminal_pv = terminal_value / (1 + discount_rate) ** 5

        return total + terminal_pv
