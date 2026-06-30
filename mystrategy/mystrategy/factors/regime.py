"""Market regime detection — BULL / BEAR / RANGE / VOLATILE."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from mystrategy.factors.base import BaseFactor, FactorMeta


class RegimeDetection(BaseFactor):
    """Detect the current market regime."""

    meta = FactorMeta(
        name="regime_detection",
        category="regime",
        display_name="市态识别",
    )

    REGIMES = ["BULL", "BEAR", "RANGE", "VOLATILE"]

    def compute(self, data: dict[str, Any]) -> dict[str, float]:
        """
        Args:
            data: should contain 'kline' (DataFrame with OHLCV) or 'index_kline'
        """
        df = data.get("kline") or data.get("index_kline")
        if df is None or df.empty or len(df) < 60:
            return {"regime": "UNKNOWN", "regime_score": 0.5}

        close = df["close"].values.astype(np.float64)

        # Trend strength: price vs MA positions
        ma20 = _sma(close, 20)
        ma60 = _sma(close, 60)
        trend_pct = (close[-1] / ma60[-1] - 1) if not np.isnan(ma60[-1]) and ma60[-1] > 0 else 0

        # Volatility: annualized 20-day volatility
        returns = np.diff(close) / close[:-1]
        vol_20d = np.std(returns[-20:]) * np.sqrt(252)

        # Market breadth: % of days above MA20 in last 60
        above_ma20 = sum(1 for i in range(-60, 0) if close[i] > ma20[i])
        breadth = above_ma20 / 60

        # Regime classification
        if trend_pct > 0.05 and vol_20d < 0.25:
            regime = "BULL"
            score = 0.85
        elif trend_pct < -0.05 and vol_20d < 0.25:
            regime = "BEAR"
            score = 0.15
        elif vol_20d > 0.35:
            regime = "VOLATILE"
            score = 0.35
        else:
            regime = "RANGE"
            score = 0.5

        return {
            "regime": regime,
            "regime_score": score,
            "trend_pct": trend_pct,
            "volatility": vol_20d,
            "breadth": breadth,
            "bull_prob": self._regime_prob(trend_pct, vol_20d, breadth, "BULL"),
            "bear_prob": self._regime_prob(trend_pct, vol_20d, breadth, "BEAR"),
            "range_prob": self._regime_prob(trend_pct, vol_20d, breadth, "RANGE"),
            "volatile_prob": self._regime_prob(trend_pct, vol_20d, breadth, "VOLATILE"),
        }

    def _regime_prob(self, trend: float, vol: float, breadth: float,
                     regime: str) -> float:
        """Simple heuristic probability for each regime."""
        if regime == "BULL":
            return min(1.0, max(0.0,
                0.4 * max(0, trend * 5) + 0.3 * max(0, 1 - vol) + 0.3 * breadth))
        elif regime == "BEAR":
            return min(1.0, max(0.0,
                0.4 * max(0, -trend * 5) + 0.3 * max(0, 1 - vol) + 0.3 * (1 - breadth)))
        elif regime == "VOLATILE":
            return min(1.0, max(0.0, vol * 2))
        else:  # RANGE
            return max(0.0, 1 - abs(trend) * 3 - vol)


def _sma(arr: np.ndarray, period: int) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=np.float64)
    if len(arr) >= period:
        cumsum = np.cumsum(np.insert(arr, 0, 0))
        result[period - 1:] = (cumsum[period:] - cumsum[:-period]) / period
    return result
