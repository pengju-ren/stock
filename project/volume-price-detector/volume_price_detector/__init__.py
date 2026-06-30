"""量价关系检测器 — 基于「背个竹筐」教学体系的买卖信号识别工具。

核心功能:
  - 9 大卖点检测（量价顶背离、天量天价、高位滞涨...）
  - 3 大买入信号（低位放量、缩量上涨锁仓、低位堆量...）
  - CLI / SDK 双模式
  - 跨市场支持（A 股 / 港股 / ETF）

快速开始:
  # CLI 模式
  python -m volume_price_detector scan 600519

  # SDK 模式
  from volume_price_detector import scan_stock
  result = scan_stock(df)
  print(result.risk_verdict)
"""

from volume_price_detector.engine import scan_stock
from volume_price_detector.models import (
    RiskLevel,
    ScanResult,
    Signal,
    SignalType,
)

__version__ = "1.0.0"
__all__ = [
    "__version__",
    "scan_stock",
    "Signal",
    "SignalType",
    "ScanResult",
    "RiskLevel",
]
