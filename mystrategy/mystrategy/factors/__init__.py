"""Factor library — 60+ factors across 8 categories.

Usage:
    from mystrategy.factors import compute_all, FACTOR_REGISTRY, TechnicalFactors

    tf = TechnicalFactors()
    scores = tf.compute({"kline": df})
"""

from mystrategy.factors.base import BaseFactor, FactorMeta
from mystrategy.factors.registry import (
    FACTOR_REGISTRY,
    list_factors,
    get_factor,
    compute_all,
)

__all__ = [
    "BaseFactor", "FactorMeta",
    "FACTOR_REGISTRY", "list_factors", "get_factor", "compute_all",
]
