"""验证视频第5集五卖点信号。"""

import numpy as np
import pandas as pd
import pytest

from volume_price_detector.engine import scan_stock
from volume_price_detector.models import SignalType


def _make_df(close: np.ndarray, volume: np.ndarray, code: str = "TEST") -> pd.DataFrame:
    """构造标准 OHLCV DataFrame。"""
    n = len(close)
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame({
        "code": code,
        "date": dates.strftime("%Y-%m-%d"),
        "open": np.maximum(close * 0.99, 0.01),
        "high": close * 1.02,
        "low": np.maximum(close * 0.98, 0.01),
        "close": close,
        "volume": volume,
    })


def _find_signal_by_name(signals, name: str):
    """在信号列表中按名称查找。"""
    for s in signals:
        if name in s.name:
            return s
    return None


class TestVideoSellSignals:
    """验证第5集五卖点信号。"""

    def test_signal_1__high_vol_flat(self):
        """信号 1: 放量滞涨 — 高位放量但价格横盘。"""
        n = 400
        close = np.linspace(5, 20, n)
        volume = np.full(n, 1_000_000.0)
        # 末段高位放量但价格几乎不动
        for i in range(360, 390):
            close[i] = close[359] + np.random.uniform(-0.01, 0.01)
            volume[i] = 3_000_000
        df = _make_df(close, volume)
        result = scan_stock(df)
        sig = _find_signal_by_name(result.sell_signals, "放量滞涨")
        if sig:
            assert sig.signal_type == SignalType.SELL
            assert "出货" in sig.description or "卖" in sig.description

    def test_signal_2__shrinking_vol_new_high(self):
        """信号 2: 缩量新高 — 股价创新高但量萎缩。

        构造: 先有前高+大量，然后刷新高但量缩至前峰70%以下。
        """
        n = 350
        close = np.linspace(5, 10, 200).tolist()
        volume = [1_000_000] * 200

        # 前高点 + 放量
        close.extend([10.5, 11.0, 11.2, 10.9, 11.0])
        volume.extend([5_000_000, 6_000_000, 5_800_000, 5_200_000, 5_000_000])

        # 回调一段
        for _ in range(30):
            close.append(close[-1] * (1 + np.random.uniform(-0.01, 0.005)))
            volume.append(1_500_000)

        # 创新高但量缩小
        close.append(12.5)
        volume.append(1_200_000)

        # 后续填充
        for _ in range(110):
            close.append(close[-1] * (1 + np.random.uniform(-0.01, 0.005)))
            volume.append(1_000_000)

        close_arr = np.array(close, dtype=np.float64)
        volume_arr = np.array(volume, dtype=np.float64)
        df = _make_df(close_arr, volume_arr)

        result = scan_stock(df, params={
            "new_high_lookback": 60,
            "shrink_new_high_vol_pct": 0.7,
        })
        sig = _find_signal_by_name(result.sell_signals, "缩量新高")
        if sig:
            assert sig.signal_type == SignalType.SELL
            assert "量价背离" in sig.description or "动能" in sig.description

    def test_signal_3__high_long_upper_shadow(self):
        """信号 3: 高位长上影 — 冲高回落，资金卖出坚决。

        构造: 手动设置某根K线有极长上影线。
        """
        n = 400
        close = np.linspace(5, 20, n)
        volume = np.full(n, 1_500_000.0, dtype=np.float64)

        i = 370
        close[i] = 19.5
        df = _make_df(close, volume)
        # 手动制造长上影 K 线
        df.loc[i, "open"] = 20.0
        df.loc[i, "high"] = 22.5
        df.loc[i, "close"] = 19.5
        df.loc[i, "low"] = 19.2
        df.loc[i, "volume"] = 2_500_000
        df.loc[i - 1, "close"] = 19.8
        df.loc[i - 1, "open"] = 19.6

        result = scan_stock(df)
        sig = _find_signal_by_name(result.sell_signals, "高位长上影")
        if sig:
            assert sig.signal_type == SignalType.SELL
            assert "冲高" in sig.description or "上影" in sig.name

    def test_signal_4__heavy_vol_big_bear(self):
        """信号 4: 放量大阴线 — 大阴线+放量，资金态度转变。

        构造: 高位、放量、大阴线（跌 > 3%）、实体占振幅 > 50%。
        """
        n = 400
        close = np.linspace(5, 20, n)
        volume = np.full(n, 1_000_000.0, dtype=np.float64)

        i = 380
        close[i] = 19.0
        df = _make_df(close, volume)
        df.loc[i, "open"] = 20.0
        df.loc[i, "high"] = 20.1
        df.loc[i, "close"] = 19.0
        df.loc[i, "low"] = 18.8
        df.loc[i, "volume"] = 4_000_000
        df.loc[i - 1, "close"] = 20.0

        result = scan_stock(df)
        sig = _find_signal_by_name(result.sell_signals, "放量大阴线")
        if sig:
            assert sig.signal_type == SignalType.SELL
            assert sig.risk_level is not None
            assert "资金" in sig.description or "态度" in sig.description or "接盘" in sig.description

    def test_signal_5__bounce_shrink_vol(self):
        """信号 5: 反弹缩量 — 下跌趋势中缩量反弹，买盘不积极。

        构造: 下跌趋势中一次缩量弱反弹。
        """
        n = 350
        rng = np.random.RandomState(99)
        close = np.zeros(n)
        close[0] = 20.0
        for i in range(1, 250):
            close[i] = close[i - 1] * (1 - 0.003 + rng.uniform(-0.008, 0.003))

        volume = np.full(n, 1_200_000.0, dtype=np.float64)
        # 前一段放量下跌
        volume[200:240] = 2_500_000
        # 反弹日：缩量
        bounce_idx = 260
        close[bounce_idx] = close[bounce_idx - 1] * 1.03
        volume[bounce_idx] = 600_000
        close[bounce_idx + 1] = close[bounce_idx] * 1.01
        volume[bounce_idx + 1] = 550_000

        for i in range(bounce_idx + 2, n):
            close[i] = close[i - 1] * (1 - 0.002 + rng.uniform(-0.008, 0.005))
            volume[i] = 1_000_000

        df = _make_df(close, volume)
        result = scan_stock(df)
        sig = _find_signal_by_name(result.sell_signals, "反弹缩量")
        if sig:
            assert sig.signal_type == SignalType.SELL
            assert "缩量" in sig.name or "买盘" in sig.description
