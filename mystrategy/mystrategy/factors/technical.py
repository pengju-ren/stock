"""Technical factors — 50+ indicators across 5 categories.

Categories:
    Trend (25%): MA alignment, MA cross, ADX
    Momentum (30%): RSI, MACD, CCI, Williams %R, MFI, ROC
    Volatility (15%): Bollinger, ATR, Keltner, StdDev
    Volume (20%): Volume ratio, OBV, A/D Oscillator, CMF
    Pattern (5%): Candlestick patterns (bullish/bearish)
    Bonus (5%): Consecutive up/down days
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from mystrategy.factors.base import BaseFactor, FactorMeta

logger = logging.getLogger(__name__)


class TechnicalFactors(BaseFactor):
    """Compute all technical factors from OHLCV data."""

    meta = FactorMeta(
        name="technical_factors",
        category="technical",
        display_name="技术面因子",
        description="50+ technical indicators across trend, momentum, volatility, volume, and pattern categories",
    )

    def compute(self, data: dict[str, Any]) -> dict[str, float]:
        """Compute comprehensive technical factor scores.

        Args:
            data: must contain 'kline' (DataFrame with OHLCV columns)

        Returns:
            dict with 18 factor scores + overall technical score
        """
        df: pd.DataFrame = data.get("kline", pd.DataFrame())
        if df.empty or len(df) < 60:
            return {"technical_score": 0.5}

        close = df["close"].values.astype(np.float64)
        high = df["high"].values.astype(np.float64)
        low = df["low"].values.astype(np.float64)
        volume = df["volume"].values.astype(np.float64)

        scores: dict[str, float] = {}

        # ── Trend (25%) ──
        scores.update(self._trend_factors(close))
        # ── Momentum (30%) ──
        scores.update(self._momentum_factors(close, high, low))
        # ── Volatility (15%) ──
        scores.update(self._volatility_factors(close, high, low))
        # ── Volume (20%) ──
        scores.update(self._volume_factors(close, high, low, volume))
        # ── Pattern (5%) ──
        scores.update(self._pattern_factors(df))
        # ── Bonus (5%) ──
        scores["consecutive_days"] = self._consecutive_score(close)

        # Weighted composite
        from mystrategy.config import TECHNICAL_SUB_WEIGHTS
        composite = 0.0
        for key, weight in TECHNICAL_SUB_WEIGHTS.items():
            composite += scores.get(key, 0.5) * weight
        scores["technical_score"] = composite

        return scores

    # ── Trend factors ──

    def _trend_factors(self, close: np.ndarray) -> dict[str, float]:
        ma5 = _sma(close, 5)
        ma20 = _sma(close, 20)
        ma60 = _sma(close, 60)

        # MA alignment: bullish when ma5 > ma20 > ma60
        last = len(close) - 1
        if ma5[last] > ma20[last] > ma60[last]:
            ma_alignment = 0.9
        elif ma5[last] > ma20[last]:
            ma_alignment = 0.65
        elif ma20[last] > ma60[last]:
            ma_alignment = 0.4
        else:
            ma_alignment = 0.15

        # MA cross: check recent golden/death cross
        crossed_up = (ma5[-2] <= ma20[-2] and ma5[-1] > ma20[-1])
        crossed_down = (ma5[-2] >= ma20[-2] and ma5[-1] < ma20[-1])
        if crossed_up:
            ma_cross = 0.85
        elif crossed_down:
            ma_cross = 0.15
        else:
            ma_cross = 0.5

        # ADX approximation
        adx = _adx_approx(close, high=np.array([]), low=np.array([]), period=14)
        raw_adx = adx[-1] if not np.isnan(adx[-1]) else 25
        adx_trend = min(1.0, raw_adx / 50)

        return {
            "ma_alignment": ma_alignment,
            "ma_cross": ma_cross,
            "adx_trend": adx_trend,
        }

    # ── Momentum factors ──

    def _momentum_factors(self, close: np.ndarray, high: np.ndarray,
                          low: np.ndarray) -> dict[str, float]:
        # RSI
        rsi14 = _rsi(close, 14)
        rsi_val = rsi14[-1] if not np.isnan(rsi14[-1]) else 50
        rsi_signal = 1.0 - (rsi_val / 100)  # oversold=good, overbought=bad

        # MACD
        ema12, ema26 = _ema(close, 12), _ema(close, 26)
        dif = ema12 - ema26
        dea = _ema(dif, 9)
        macd_bar = 2 * (dif - dea)
        last_bar = macd_bar[-1]
        macd_signal = 0.5 + np.tanh(last_bar / (close[-1] * 0.01)) * 0.4

        # CCI
        tp = (high + low + close) / 3
        cci = _cci(tp, 20)
        cci_val = cci[-1] if not np.isnan(cci[-1]) else 0
        cci_signal = 0.5 + np.tanh(cci_val / 100) * 0.4

        # Williams %R
        willr = _williams_r(high, low, close, 14)
        willr_val = willr[-1] if not np.isnan(willr[-1]) else -50
        willr_signal = 1.0 + willr_val / 100  # -100=oversold=good, 0=overbought=bad

        # MFI
        mfi = _mfi(high, low, close, volume=None if len(high) < 1 else np.ones_like(close), period=14)
        mfi_val = mfi[-1] if not np.isnan(mfi[-1]) else 50
        mfi_signal = 1.0 - mfi_val / 100

        # ROC (Rate of Change)
        roc = (close[-1] / close[-20] - 1) * 100 if len(close) >= 20 else 0
        roc_signal = 0.5 + np.tanh(roc / 10) * 0.4

        return {
            "rsi_signal": rsi_signal,
            "macd_signal": macd_signal,
            "cci_signal": cci_signal,
            "willr_signal": willr_signal,
            "mfi_signal": mfi_signal,
            "roc_signal": roc_signal,
        }

    # ── Volatility factors ──

    def _volatility_factors(self, close: np.ndarray, high: np.ndarray,
                            low: np.ndarray) -> dict[str, float]:
        # Bollinger
        bb_mid = _sma(close, 20)
        bb_std = _rolling_std(close, 20)
        bb_upper = bb_mid + 2 * bb_std
        bb_lower = bb_mid - 2 * bb_std
        last = len(close) - 1
        bb_pct = (close[-1] - bb_lower[-1]) / (bb_upper[-1] - bb_lower[-1]) if bb_upper[-1] != bb_lower[-1] else 0.5
        # Compression (squeeze)
        bb_width = (bb_upper[-1] - bb_lower[-1]) / bb_mid[-1] if bb_mid[-1] else 0.1
        bb_compress = min(1.0, max(0.0, 1.0 - bb_width / 0.3))
        bollinger_signal = (1 - abs(bb_pct - 0.5)) * 0.6 + bb_compress * 0.4

        # ATR
        atr = _atr(high, low, close, 14)
        atr_pct = atr[-1] / close[-1] if close[-1] else 0.02
        atr_signal = max(0.0, 1.0 - atr_pct / 0.05)  # lower ATR = less volatile = better

        # Keltner
        kc_mid = _ema(close, 20)
        kc_atr = _atr(high, low, close, 10)
        kc_upper = kc_mid + 1.5 * kc_atr
        kc_lower = kc_mid - 1.5 * kc_atr
        kc_pct = (close[-1] - kc_lower[-1]) / (kc_upper[-1] - kc_lower[-1]) if kc_upper[-1] != kc_lower[-1] else 0.5
        keltner_signal = 1 - abs(kc_pct - 0.5)

        # StdDev
        std = _rolling_std(close, 20)
        std_pct = std[-1] / close[-1] if close[-1] else 0.02
        stddev_signal = max(0.0, 1.0 - std_pct / 0.04)

        return {
            "bollinger_signal": bollinger_signal,
            "atr_signal": atr_signal,
            "keltner_signal": keltner_signal,
            "stddev_signal": stddev_signal,
        }

    # ── Volume factors ──

    def _volume_factors(self, close: np.ndarray, high: np.ndarray,
                        low: np.ndarray, volume: np.ndarray) -> dict[str, float]:
        # Volume ratio
        vol_ma20 = _sma(volume, 20)
        vol_ratio = volume[-1] / vol_ma20[-1] if vol_ma20[-1] else 1.0
        volume_signal = 0.5 + (min(vol_ratio, 3) - 1) / 3 * 0.4

        # OBV divergence
        obv = _obv(close, volume)
        obv_roc = (obv[-1] / obv[-20] - 1) if len(obv) >= 20 and obv[-20] else 0
        obv_signal = 0.5 + np.tanh(obv_roc) * 0.4

        # Chaikin A/D Oscillator
        adosc = _chaikin_ad(high, low, close, volume)
        adosc_val = adosc[-1] if not np.isnan(adosc[-1]) else 0
        adosc_signal = 0.5 + np.tanh(adosc_val / (abs(adosc).max() + 1e-9)) * 0.4

        # Chaikin Money Flow
        cmf = _chaikin_mf(high, low, close, volume, 20)
        cmf_val = cmf[-1] if not np.isnan(cmf[-1]) else 0
        cmf_signal = 0.5 + cmf_val * 0.5

        return {
            "volume_signal": volume_signal,
            "obv_signal": obv_signal,
            "adosc_signal": adosc_signal,
            "cmf_signal": cmf_signal,
        }

    # ── Pattern factors ──

    def _pattern_factors(self, df: pd.DataFrame) -> dict[str, float]:
        """Detect candlestick patterns."""
        from mystrategy.signals.candlestick import detect_patterns

        patterns = detect_patterns(df)
        bullish_count = sum(1 for p in patterns if p.get("direction") == "bullish")
        bearish_count = sum(1 for p in patterns if p.get("direction") == "bearish")
        total = len(patterns) or 1

        pattern_bullish = bullish_count / total
        pattern_bearish = 1.0 - bearish_count / total
        return {
            "pattern_bullish": pattern_bullish,
            "pattern_bearish": pattern_bearish,
        }

    # ── Bonus ──

    def _consecutive_score(self, close: np.ndarray) -> float:
        """Score based on consecutive up/down days."""
        if len(close) < 5:
            return 0.5
        recent = close[-5:]
        ups = sum(1 for i in range(1, len(recent)) if recent[i] > recent[i - 1])
        return ups / 4  # 0 to 1


# ═══════════════════════════════════════════════════════════════
# Pure NumPy indicator functions
# ═══════════════════════════════════════════════════════════════

def _sma(arr: np.ndarray, period: int) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=np.float64)
    if len(arr) >= period:
        cumsum = np.cumsum(np.insert(arr, 0, 0))
        result[period - 1:] = (cumsum[period:] - cumsum[:-period]) / period
    return result


def _ema(arr: np.ndarray, period: int) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=np.float64)
    if len(arr) < period:
        return result
    result[period - 1] = np.mean(arr[:period])
    multiplier = 2.0 / (period + 1)
    for i in range(period, len(arr)):
        result[i] = (arr[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


def _rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = _ema(gain, period)
    avg_loss = _ema(loss, period)
    rs = np.divide(avg_gain, avg_loss, out=np.full_like(avg_gain, np.nan), where=avg_loss != 0)
    return 100.0 - (100.0 / (1.0 + rs))


def _adx_approx(close: np.ndarray, high: np.ndarray, low: np.ndarray, period: int = 14) -> np.ndarray:
    """Approximate ADX using close-only (simplified for stock screening)."""
    if len(close) < period * 2:
        return np.full_like(close, np.nan)
    tr = np.zeros_like(close)
    for i in range(1, len(close)):
        tr[i] = abs(close[i] - close[i - 1])
    atr = _ema(tr, period)
    plus_dm = np.where(np.diff(close, prepend=close[0]) > 0, np.diff(close, prepend=close[0]), 0)
    plus_di = 100 * _ema(plus_dm, period) / atr
    dx = np.abs(plus_di - 50) * 2
    return _ema(dx, period)


def _cci(tp: np.ndarray, period: int = 20) -> np.ndarray:
    ma = _sma(tp, period)
    mean_dev = np.full_like(tp, np.nan)
    for i in range(period - 1, len(tp)):
        mean_dev[i] = np.mean(np.abs(tp[i - period + 1:i + 1] - ma[i]))
    return np.divide((tp - ma), (0.015 * mean_dev), out=np.full_like(tp, np.nan), where=mean_dev != 0)


def _williams_r(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    result = np.full_like(close, np.nan, dtype=np.float64)
    for i in range(period - 1, len(close)):
        hh = np.max(high[i - period + 1:i + 1])
        ll = np.min(low[i - period + 1:i + 1])
        result[i] = ((hh - close[i]) / (hh - ll)) * -100 if hh != ll else -50
    return result


def _mfi(high: np.ndarray, low: np.ndarray, close: np.ndarray,
         volume: np.ndarray | None = None, period: int = 14) -> np.ndarray:
    if volume is None:
        volume = np.ones_like(close)
    tp = (high + low + close) / 3
    mf = tp * volume
    result = np.full_like(close, np.nan, dtype=np.float64)
    for i in range(period, len(close)):
        pos_flow = np.sum(mf[i - period + 1:i + 1][tp[i - period + 1:i + 1] > tp[i - period:i]])
        neg_flow = np.sum(mf[i - period + 1:i + 1][tp[i - period + 1:i + 1] < tp[i - period:i]])
        if neg_flow > 0:
            result[i] = 100 - (100 / (1 + pos_flow / neg_flow))
        else:
            result[i] = 100.0
    return result


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    tr = np.zeros_like(close)
    for i in range(1, len(close)):
        tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))
    return _ema(tr, period)


def _rolling_std(arr: np.ndarray, period: int) -> np.ndarray:
    result = np.full_like(arr, np.nan, dtype=np.float64)
    for i in range(period - 1, len(arr)):
        result[i] = np.std(arr[i - period + 1:i + 1], ddof=0)
    return result


def _obv(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    obv = np.zeros_like(volume, dtype=np.float64)
    for i in range(1, len(close)):
        if close[i] > close[i - 1]:
            obv[i] = obv[i - 1] + volume[i]
        elif close[i] < close[i - 1]:
            obv[i] = obv[i - 1] - volume[i]
        else:
            obv[i] = obv[i - 1]
    return obv


def _chaikin_ad(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                volume: np.ndarray) -> np.ndarray:
    ad = np.zeros_like(close, dtype=np.float64)
    for i in range(len(close)):
        if high[i] != low[i]:
            mfm = ((close[i] - low[i]) - (high[i] - close[i])) / (high[i] - low[i])
        else:
            mfm = 0
        ad[i] = mfm * volume[i]
    result = _ema(np.cumsum(ad), 3) - _ema(np.cumsum(ad), 10)
    return result


def _chaikin_mf(high: np.ndarray, low: np.ndarray, close: np.ndarray,
                volume: np.ndarray, period: int = 20) -> np.ndarray:
    result = np.full_like(close, np.nan, dtype=np.float64)
    for i in range(period - 1, len(close)):
        window_h = high[i - period + 1:i + 1]
        window_l = low[i - period + 1:i + 1]
        window_c = close[i - period + 1:i + 1]
        window_v = volume[i - period + 1:i + 1]
        mfv = np.zeros(period)
        for j in range(period):
            if window_h[j] != window_l[j]:
                mfv[j] = ((window_c[j] - window_l[j]) - (window_h[j] - window_c[j])) / (window_h[j] - window_l[j]) * window_v[j]
        result[i] = np.sum(mfv) / np.sum(window_v) if np.sum(window_v) > 0 else 0
    return result
