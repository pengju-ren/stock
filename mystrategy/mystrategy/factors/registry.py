"""Factor registry — discoverable catalog of all available factors."""

from __future__ import annotations

from typing import Type

from mystrategy.factors.base import BaseFactor, FactorMeta
from mystrategy.factors.technical import TechnicalFactors
from mystrategy.factors.fundamental import FundamentalFactors
from mystrategy.factors.capital_flow import CapitalFlowFactors
from mystrategy.factors.quality import FScore, MScore, RedFlags
from mystrategy.factors.valuation import ValuationFactors
from mystrategy.factors.regime import RegimeDetection


# All registered factor classes
FACTOR_REGISTRY: dict[str, Type[BaseFactor]] = {
    "technical": TechnicalFactors,
    "fundamental": FundamentalFactors,
    "capital_flow": CapitalFlowFactors,
    "f_score": FScore,
    "m_score": MScore,
    "red_flags": RedFlags,
    "valuation": ValuationFactors,
    "regime": RegimeDetection,
}


def list_factors(category: str | None = None) -> list[FactorMeta]:
    """List all registered factors, optionally filtered by category."""
    result = []
    for key, cls in FACTOR_REGISTRY.items():
        meta = cls.meta
        if category is None or meta.category == category:
            result.append(meta)
    return result


def get_factor(name: str) -> Type[BaseFactor] | None:
    """Get a factor class by name."""
    return FACTOR_REGISTRY.get(name)


def compute_all(data: dict) -> dict[str, dict[str, float]]:
    """Compute all registered factors against the given data.

    Returns:
        dict[factor_name] -> {sub_factor: value, ...}
    """
    results = {}
    for name, cls in FACTOR_REGISTRY.items():
        try:
            instance = cls()
            results[name] = instance.compute(data)
        except Exception as e:
            results[name] = {"error": str(e)}
    return results
