"""Factor base classes.

A Factor is a computable metric from market data. It has:
- name: unique identifier
- category: 'technical', 'fundamental', 'capital_flow', 'sentiment', 'quality', 'valuation', 'regime', 'industry'
- compute(data) -> dict[str, float]: compute the factor value(s)
- thresholds: validation thresholds from ai-berkshire research
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd


@dataclass
class FactorMeta:
    """Metadata for a single factor."""
    name: str
    category: str
    display_name: str = ""
    description: str = ""
    version: str = "1.0"
    # Thresholds from ai-berkshire
    thresholds: dict[str, float] = field(default_factory=dict)
    # Is higher better?
    higher_is_better: bool = True


class BaseFactor:
    """Base class for all factors.

    Subclasses implement compute() which takes market data and returns
    a dict of factor_name -> value.
    """

    meta: FactorMeta

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, 'meta'):
            cls.meta = FactorMeta(
                name=cls.__name__.lower(),
                category="unknown",
            )

    def compute(self, data: dict[str, Any]) -> dict[str, float]:
        """Compute factor values from input data.

        Args:
            data: dict with market data (kline_df, financials, etc.)

        Returns:
            dict[factor_name] -> float value
        """
        raise NotImplementedError

    def validate(self, values: dict[str, float]) -> dict[str, str]:
        """Validate factor values against thresholds. Returns {name: status}."""
        result = {}
        for name, threshold in self.meta.thresholds.items():
            if name in values:
                if self.meta.higher_is_better:
                    status = "PASS" if values[name] >= threshold else "FAIL"
                else:
                    status = "PASS" if values[name] <= threshold else "FAIL"
                result[name] = status
        return result

    def normalize(self, raw_value: float, min_val: float = 0,
                  max_val: float = 100) -> float:
        """Normalize a factor value to [0, 1] range."""
        if max_val == min_val:
            return 0.5
        return max(0.0, min(1.0, (raw_value - min_val) / (max_val - min_val)))

    def percentile_score(self, value: float, all_values: list[float]) -> float:
        """Score a value by its percentile rank among peers."""
        if not all_values:
            return 0.5
        sorted_vals = sorted(all_values)
        rank = sum(1 for v in sorted_vals if v <= value)
        return rank / len(sorted_vals)
