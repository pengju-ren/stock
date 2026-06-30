"""纯 NumPy 技术指标 — 无外部依赖。

所有函数接受 numpy 数组，返回 numpy 数组。
设计原则：零 TA-Lib 依赖，零 pandas 依赖（指标层），高性能向量化运算。
"""

import numpy as np


# ═══════════════════════════════════════════════════════════════
#  移动平均线
# ═══════════════════════════════════════════════════════════════

def sma(data: np.ndarray, period: int) -> np.ndarray:
    """简单移动平均。"""
    result = np.full_like(data, np.nan, dtype=np.float64)
    if len(data) < period:
        return result
    cumsum = np.cumsum(np.insert(data.astype(np.float64), 0, 0.0))
    result[period - 1:] = (cumsum[period:] - cumsum[:-period]) / period
    return result


def ema(data: np.ndarray, period: int) -> np.ndarray:
    """指数移动平均。"""
    result = np.full_like(data, np.nan, dtype=np.float64)
    if len(data) < period:
        return result
    result[period - 1] = np.mean(data[:period])
    multiplier = 2.0 / (period + 1)
    for i in range(period, len(data)):
        result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


# ═══════════════════════════════════════════════════════════════
#  滚动极值
# ═══════════════════════════════════════════════════════════════

def rolling_max(data: np.ndarray, period: int) -> np.ndarray:
    """滚动最大值。"""
    result = np.full_like(data, np.nan, dtype=np.float64)
    if len(data) < period:
        return result
    for i in range(period - 1, len(data)):
        result[i] = float(np.max(data[i - period + 1 : i + 1]))
    return result


def rolling_min(data: np.ndarray, period: int) -> np.ndarray:
    """滚动最小值。"""
    result = np.full_like(data, np.nan, dtype=np.float64)
    if len(data) < period:
        return result
    for i in range(period - 1, len(data)):
        result[i] = float(np.min(data[i - period + 1 : i + 1]))
    return result


def rolling_argmax(data: np.ndarray, period: int) -> np.ndarray:
    """滚动最大值的位置（相对于窗口起始的偏移量）。"""
    result = np.full_like(data, -1, dtype=np.intp)
    if len(data) < period:
        return result
    for i in range(period - 1, len(data)):
        window = data[i - period + 1 : i + 1]
        result[i] = int(np.argmax(window))
    return result


# ═══════════════════════════════════════════════════════════════
#  波动率
# ═══════════════════════════════════════════════════════════════

def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray,
        period: int = 14) -> np.ndarray:
    """平均真实波幅 (Average True Range)。"""
    n = len(close)
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = float(high[0] - low[0])
    for i in range(1, n):
        tr[i] = float(max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        ))
    return ema(tr, period)


# ═══════════════════════════════════════════════════════════════
#  量价指标
# ═══════════════════════════════════════════════════════════════

def volume_ma(volume: np.ndarray, period: int) -> np.ndarray:
    """成交量移动平均。"""
    return sma(volume, period)


def volume_ratio(volume: np.ndarray, period: int = 20) -> np.ndarray:
    """量比 = 当前量 / N日均量。"""
    ma = volume_ma(volume, period)
    # 避免除零
    safe_ma = np.where(ma > 0, ma, np.nan)
    return volume.astype(np.float64) / safe_ma


# ═══════════════════════════════════════════════════════════════
#  趋势/位置判断
# ═══════════════════════════════════════════════════════════════

def is_uptrend(close: np.ndarray, idx: int,
               fast: int = 20, slow: int = 60) -> bool:
    """判断 index 位置是否处于上升趋势。

    条件: MA(fast) > MA(slow) 且 MA(fast) 近10日上行。
    """
    need_bars = slow + 20
    if idx < need_bars:
        return False
    ma_fast = ema(close[:idx + 1], fast)
    ma_slow = ema(close[:idx + 1], slow)
    f = ma_fast[idx]
    s = ma_slow[idx]
    f_10 = ma_fast[idx - 10] if idx >= 10 else np.nan
    if np.isnan(f) or np.isnan(s) or np.isnan(f_10):
        return False
    return f > s and f > f_10


def is_downtrend(close: np.ndarray, idx: int,
                 fast: int = 20, slow: int = 60) -> bool:
    """判断是否处于下跌趋势。"""
    need_bars = slow + 20
    if idx < need_bars:
        return False
    ma_fast = ema(close[:idx + 1], fast)
    ma_slow = ema(close[:idx + 1], slow)
    f = ma_fast[idx]
    s = ma_slow[idx]
    f_10 = ma_fast[idx - 10] if idx >= 10 else np.nan
    if np.isnan(f) or np.isnan(s) or np.isnan(f_10):
        return False
    return f < s and f < f_10


def price_position(close: np.ndarray, idx: int,
                   lookback: int = 120) -> float:
    """价格在 lookback 日内的分位数 (0~1)。"""
    if idx < lookback:
        return 0.5
    window = close[idx - lookback : idx + 1]
    return float(np.sum(close[idx] >= window) / len(window))


def is_price_high(close: np.ndarray, idx: int,
                  lookback: int = 120, threshold: float = 0.70) -> bool:
    """价格是否处于高位（分位数 > threshold）。"""
    return price_position(close, idx, lookback) > threshold


def is_price_low(close: np.ndarray, idx: int,
                 lookback: int = 120, threshold: float = 0.30) -> bool:
    """价格是否处于低位（分位数 < threshold）。"""
    return price_position(close, idx, lookback) < threshold


# ═══════════════════════════════════════════════════════════════
#  密集成交区检测
# ═══════════════════════════════════════════════════════════════

def upper_shadow_ratio(
    high: np.ndarray, open_: np.ndarray, close: np.ndarray,
) -> np.ndarray:
    """上影线比例 = 上影线长度 / 实体长度。

    Returns:
        与输入等长的数组。值 > 1 表示上影线比实体长。
        十字星/极小实体会产生极大值（用 max(body, 0.001*close) 防止除零）。
    """
    n = len(close)
    result = np.full(n, np.nan, dtype=np.float64)
    for i in range(n):
        body = abs(close[i] - open_[i])
        upper = high[i] - max(open_[i], close[i])
        safe_body = max(body, close[i] * 0.001, 1e-8)
        result[i] = float(upper / safe_body)
    return result


def lower_shadow_ratio(
    high: np.ndarray, open_: np.ndarray, close: np.ndarray,
) -> np.ndarray:
    """下影线比例 = 下影线长度 / 实体长度。"""
    n = len(close)
    result = np.full(n, np.nan, dtype=np.float64)
    for i in range(n):
        body = abs(close[i] - open_[i])
        lower = min(open_[i], close[i]) - low[i]
        safe_body = max(body, close[i] * 0.001, 1e-8)
        result[i] = float(lower / safe_body)
    return result


def find_volume_clusters(
    volume: np.ndarray,
    price: np.ndarray,
    idx: int,
    lookback: int = 250,
) -> list[tuple[float, float]]:
    """找出高成交量密集区域（价格区间）。

    将历史数据按成交量排序，取前 20% 高量日，将这些日的价格聚类。

    Returns:
        list of (price_low, price_high) — 密集成交区价格范围
    """
    if idx < lookback or idx >= len(price):
        return []

    start = idx - lookback
    end = idx + 1
    window_vol = volume[start:end].astype(np.float64)
    window_price = price[start:end].astype(np.float64)

    valid = ~np.isnan(window_vol)
    window_vol = window_vol[valid]
    window_price = window_price[valid]

    if len(window_vol) < 20:
        return []

    threshold = float(np.percentile(window_vol, 80))
    high_vol_mask = window_vol >= threshold
    high_vol_prices = window_price[high_vol_mask]

    if len(high_vol_prices) < 5:
        return []

    sorted_prices = np.sort(high_vol_prices)
    clusters: list[tuple[float, float]] = []

    current_start = float(sorted_prices[0])
    current_end = float(sorted_prices[0])
    price_range = float(sorted_prices[-1] - sorted_prices[0])
    gap_threshold = price_range * 0.15 if price_range > 0 else 0.01

    for i in range(1, len(sorted_prices)):
        p = float(sorted_prices[i])
        if p - current_end < gap_threshold:
            current_end = p
        else:
            if current_end - current_start > 0:
                clusters.append((current_start, current_end))
            current_start = p
            current_end = p

    if current_end - current_start > 0:
        clusters.append((current_start, current_end))

    return clusters
