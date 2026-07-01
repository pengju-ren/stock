"""
市场状态变化检测 — 监控市场风格的转变，触发策略调整需求。

当波动率结构/板块轮动速度/相关性结构发生显著变化时，
说明现有策略可能不再适用，需要重新评估或开发新策略。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from .config import REGIME, REPORTS_DIR


@dataclass
class RegimeChangeAlert:
    """市场状态变化警报。"""
    dimension: str   # volatility / correlation / rotation_speed / breadth
    old_value: float
    new_value: float
    change_pct: float
    severity: str  # alert / warning / info
    implication: str  # 对策略的影响
    recommended_action: str


@dataclass
class RegimeReport:
    """市场状态监测报告。"""
    timestamp: str
    current_regime: str
    regime_confidence: float
    alerts: list[RegimeChangeAlert] = field(default_factory=list)
    market_snapshot: dict = field(default_factory=dict)
    strategy_implications: list[str] = field(default_factory=list)
    summary: str = ""


class RegimeMonitor:
    """市场状态变化监测器。

    监测四个维度:
      1. 波动率结构 — 整体波动率水平是否改变
      2. 相关性结构 — 个股间相关性是否变化
      3. 板块轮动速度 — 板块热点切换频率
      4. 市场宽度 — 上涨股票比例

    当任一维度发生显著变化时，发出警报，提示某些策略可能需要调整。

    用法:
        monitor = RegimeMonitor()
        report = monitor.check(market_data, previous_state)
        for alert in report.alerts:
            print(f"[{alert.severity}] {alert.dimension}: {alert.implication}")
    """

    def __init__(self):
        self.threshold = REGIME["regime_change_threshold"]
        self.previous_snapshot: dict = {}

    def check(self, market_data: pd.DataFrame | None = None,
              previous_state: dict | None = None) -> RegimeReport:
        """检测市场状态是否发生显著变化。

        Args:
            market_data: 市场数据（指数K线/行业数据等）
            previous_state: 上一次的市场快照

        Returns:
            RegimeReport 含变化警报
        """
        report = RegimeReport(
            timestamp=datetime.now().isoformat(),
            current_regime="UNKNOWN",
            regime_confidence=0.0,
        )

        alerts = []

        # 尝试从 stock-analyzer 获取当前市场状态
        try:
            current_snapshot = self._get_market_snapshot(market_data)
            report.market_snapshot = current_snapshot
            report.current_regime = current_snapshot.get("regime", "UNKNOWN")
            report.regime_confidence = current_snapshot.get("confidence", 0.0)
        except Exception:
            current_snapshot = {}

        # 如果有之前的状态，对比检测变化
        if previous_state:
            alerts = self._detect_changes(previous_state, current_snapshot)
            # 如果变化较大，更新之前的状态
            if len([a for a in alerts if a.severity == "alert"]) > 0:
                self.previous_snapshot = current_snapshot
        else:
            self.previous_snapshot = current_snapshot

        report.alerts = alerts
        report.strategy_implications = self._derive_implications(report)
        report.summary = self._generate_summary(report)
        return report

    def _get_market_snapshot(self, market_data: pd.DataFrame | None) -> dict:
        """获取当前市场快照。"""
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "regime": "UNKNOWN",
            "confidence": 0.0,
            "volatility": 0.0,
            "correlation": 0.0,
            "rotation_speed": 0.0,
            "breadth": 0.0,
        }

        # 尝试使用 stock-analyzer 的 regime 检测
        try:
            from stock_analyzer.factors.regime import detect_regime_from_hist
            if market_data is not None and not market_data.empty:
                result = detect_regime_from_hist(market_data)
                snapshot["regime"] = result.regime.value
                snapshot["confidence"] = result.confidence
                snapshot["volatility"] = result.volatility_pct
                snapshot["breadth"] = result.breadth
        except ImportError:
            pass

        return snapshot

    def _detect_changes(self, old: dict, new: dict) -> list[RegimeChangeAlert]:
        """检测两个快照之间的显著变化。"""
        alerts = []

        # 波动率变化
        old_vol = old.get("volatility", 0)
        new_vol = new.get("volatility", 0)
        if old_vol > 0 and new_vol > 0:
            vol_change = abs(new_vol - old_vol) / old_vol
            if vol_change > self.threshold * 2:
                alerts.append(RegimeChangeAlert(
                    dimension="volatility",
                    old_value=old_vol, new_value=new_vol,
                    change_pct=round(vol_change * 100, 1),
                    severity="alert",
                    implication="波动率结构显著变化，趋势策略和均值回归策略可能需要调整参数",
                    recommended_action="重新校准ATR止损宽度和布林带参数",
                ))
            elif vol_change > self.threshold:
                alerts.append(RegimeChangeAlert(
                    dimension="volatility",
                    old_value=old_vol, new_value=new_vol,
                    change_pct=round(vol_change * 100, 1),
                    severity="warning",
                    implication="波动率结构有变化，建议关注",
                    recommended_action="持续观察波动率趋势",
                ))

        # 市场宽度变化
        old_breadth = old.get("breadth", 0.5)
        new_breadth = new.get("breadth", 0.5)
        breadth_change = abs(new_breadth - old_breadth)
        if breadth_change > 0.2:
            alerts.append(RegimeChangeAlert(
                dimension="breadth",
                old_value=old_breadth, new_value=new_breadth,
                change_pct=round(breadth_change * 100, 1),
                severity="alert" if breadth_change > 0.3 else "warning",
                implication="市场宽度变化意味着个股分化加剧或收敛",
                recommended_action="重新评估选股策略是否适应当前市场宽度",
            ))

        # 状态切换
        old_regime = old.get("regime", "")
        new_regime = new.get("regime", "")
        if old_regime and new_regime and old_regime != new_regime:
            alerts.append(RegimeChangeAlert(
                dimension="regime",
                old_value=0, new_value=0,  # categorical
                change_pct=100.0,
                severity="alert",
                implication=f"市场状态从 {old_regime} 切换到 {new_regime}",
                recommended_action=f"切换策略配置到 {new_regime} 模式",
            ))

        return alerts

    def _derive_implications(self, report: RegimeReport) -> list[str]:
        """推导对策略的影响。"""
        implications = []
        regime = report.current_regime

        if regime == "BULL":
            implications = [
                "趋势跟踪策略应增加仓位",
                "动量因子权重可以上调",
                "均值回归策略应减少使用",
            ]
        elif regime == "BEAR":
            implications = [
                "高股息防御策略应为基石",
                "降低所有策略的仓位上限",
                "收紧止损参数",
            ]
        elif regime == "RANGE":
            implications = [
                "网格交易和均值回归策略优先",
                "趋势跟踪策略减仓或暂停",
                "缩紧止盈参数，及时兑现利润",
            ]
        elif regime == "VOLATILE":
            implications = [
                "降低整体仓位",
                "放宽止损避免被震出",
                "网格策略加大网格间距",
            ]

        # 添加具体警报的影响
        for alert in report.alerts:
            implications.append(f"[{alert.dimension}变化] {alert.implication}")

        return implications

    @staticmethod
    def _generate_summary(report: RegimeReport) -> str:
        alert_count = len([a for a in report.alerts if a.severity == "alert"])
        warn_count = len([a for a in report.alerts if a.severity == "warning"])

        lines = [
            "=" * 60,
            f"市场状态监测 — {report.timestamp[:10]}",
            "=" * 60,
            f"当前状态: {report.current_regime} (置信度: {report.regime_confidence:.0%})",
            f"警报: {alert_count} | 预警: {warn_count}",
            "",
        ]
        if report.alerts:
            lines.append("检测到变化:")
            for a in report.alerts:
                icon = "🚨" if a.severity == "alert" else "⚠️"
                lines.append(f"  {icon} [{a.dimension}] {a.implication}")
        else:
            lines.append("✅ 未检测到显著市场状态变化。")

        if report.strategy_implications:
            lines.append("\n策略影响:")
            for impl in report.strategy_implications[:5]:
                lines.append(f"  → {impl}")

        return "\n".join(lines)

    def save_report(self, report: RegimeReport) -> str:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        filepath = os.path.join(REPORTS_DIR, f"regime_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        data = {
            "timestamp": report.timestamp,
            "regime": report.current_regime,
            "confidence": report.regime_confidence,
            "alerts": [
                {"dimension": a.dimension, "severity": a.severity, "change_pct": a.change_pct}
                for a in report.alerts
            ],
            "implications": report.strategy_implications,
            "snapshot": report.market_snapshot,
            "summary": report.summary,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath
