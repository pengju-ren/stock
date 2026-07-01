"""
策略绩效审计 — 评估所有策略的近期表现，找出最弱环节。

这是步骤① FIND WEAKNESS 的核心模块之一。
分析每个策略的年化收益/夏普/最大回撤/胜率/盈亏比/连续亏损月数，
输出按严重程度排序的弱点清单。
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from .config import STRATEGY_HEALTH, EVOLVE_ROOT, STOCK_ANALYZER_SRC
from .state import EvolutionState

# 将 stock-analyzer 加入 sys.path（只读引用，不修改）
if STOCK_ANALYZER_SRC not in sys.path:
    sys.path.insert(0, os.path.dirname(STOCK_ANALYZER_SRC))


@dataclass
class StrategyHealthReport:
    """单个策略的健康报告。"""
    strategy_name: str
    overall_health: str  # healthy / warning / critical
    metrics: dict[str, Any] = field(default_factory=dict)
    weaknesses: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class AuditReport:
    """完整的策略审计报告。"""
    timestamp: str
    strategies_assessed: int
    healthy_count: int = 0
    warning_count: int = 0
    critical_count: int = 0
    strategy_reports: list[StrategyHealthReport] = field(default_factory=list)
    top_weaknesses: list[dict] = field(default_factory=list)
    summary: str = ""


class StrategyAuditor:
    """策略绩效审计器。

    评估所有已知策略的近期表现，参考 stock-analyzer 的历史回测数据
    和 evolve/strategies/ 下的进化策略。核心输出是按严重程度排序的弱点列表。

    用法:
        auditor = StrategyAuditor()
        report = auditor.run_audit()
        for weakness in report.top_weaknesses:
            print(f"{weakness['severity']}: {weakness['description']}")
    """

    def __init__(self):
        self.known_strategies = self._discover_strategies()

    def _discover_strategies(self) -> list[str]:
        """发现所有可用的策略。"""
        strategies = []

        # 来自 stock-analyzer 的策略
        try:
            from stock_analyzer.strategies.base import list_strategies
            strategies.extend(list_strategies())
        except ImportError:
            # 回退到手动列表
            strategies.extend([
                "multi_factor_rotation", "etf_sector_rotation", "grid_trading",
                "mean_reversion", "bollinger_grid", "high_dividend_defense",
                "regime_adaptive", "momentum_breakout", "swing_trend",
                "trend_following", "volume_price", "rotation", "pca_selection",
            ])

        # 来自 evolve/strategies/ 的进化策略
        evolve_strategies_dir = os.path.join(EVOLVE_ROOT, "strategies")
        if os.path.isdir(evolve_strategies_dir):
            for fname in os.listdir(evolve_strategies_dir):
                if fname.endswith(".py") and not fname.startswith("_"):
                    strategies.append(f"evolve.{fname[:-3]}")

        return sorted(set(strategies))

    def run_audit(self, backtest_data: pd.DataFrame | None = None,
                  performance_log: dict | None = None) -> AuditReport:
        """执行完整策略审计。

        Args:
            backtest_data: 可选的历史回测数据
            performance_log: 可选的近期绩效记录

        Returns:
            AuditReport 包含所有策略的健康评估
        """
        report = AuditReport(
            timestamp=datetime.now().isoformat(),
            strategies_assessed=len(self.known_strategies),
        )

        all_weaknesses = []

        for strategy_name in self.known_strategies:
            health = self._assess_strategy(strategy_name, backtest_data, performance_log)
            report.strategy_reports.append(health)

            # 计数
            if health.overall_health == "healthy":
                report.healthy_count += 1
            elif health.overall_health == "warning":
                report.warning_count += 1
            else:
                report.critical_count += 1

            # 收集弱点
            for w in health.weaknesses:
                all_weaknesses.append({
                    "strategy": strategy_name,
                    "health": health.overall_health,
                    "weakness": w,
                })

        # 按严重程度排序弱点
        severity_order = {"critical": 0, "warning": 1, "healthy": 2}
        all_weaknesses.sort(key=lambda w: severity_order.get(w["health"], 3))

        report.top_weaknesses = all_weaknesses[:10]

        # 生成摘要
        report.summary = self._generate_summary(report)

        return report

    def _assess_strategy(self, name: str, backtest_data: pd.DataFrame | None,
                         perf_log: dict | None) -> StrategyHealthReport:
        """评估单个策略。"""
        weaknesses = []
        strengths = []
        metrics = {}

        # 尝试从 stock-analyzer 获取策略回测数据
        try:
            if name.startswith("evolve."):
                # 进化策略 — 从 evolve/strategies/ 导入
                metrics = self._get_evolve_strategy_metrics(name)
            else:
                # 原始策略 — 尝试运行快速回测
                metrics = self._get_builtin_strategy_metrics(name)
        except Exception as e:
            metrics = {"error": str(e), "annual_return": 0, "sharpe_ratio": 0,
                        "max_drawdown": 0, "win_rate": 0, "profit_factor": 0}

        # 也检查 performance_log（如果有）
        if perf_log and name in perf_log:
            metrics.update(perf_log[name])

        # --- 诊断逻辑 ---
        ann_ret = metrics.get("annual_return", 0)
        sharpe = metrics.get("sharpe_ratio", 0)
        max_dd = metrics.get("max_drawdown", 0)
        win_rate = metrics.get("win_rate", 0)
        profit_factor = metrics.get("profit_factor", 0)
        cons_lose = metrics.get("consecutive_losing_months", 0)

        # 年化收益检查
        if ann_ret < STRATEGY_HEALTH["min_annual_return"]:
            weaknesses.append(f"年化收益为负 ({ann_ret:.1f}%)")

        # 夏普检查
        if sharpe < STRATEGY_HEALTH["min_sharpe_trigger"]:
            weaknesses.append(f"夏普比率过低 ({sharpe:.2f})")
        elif sharpe > 1.5:
            strengths.append(f"夏普比率优秀 ({sharpe:.2f})")

        # 回撤检查
        if max_dd > STRATEGY_HEALTH["max_drawdown_trigger"]:
            weaknesses.append(f"最大回撤过大 ({max_dd:.1f}%)")

        # 胜率检查
        if win_rate < 0.35:
            weaknesses.append(f"胜率偏低 ({win_rate:.1%})")
        elif win_rate > 0.55:
            strengths.append(f"胜率良好 ({win_rate:.1%})")

        # 连续亏损
        if cons_lose >= STRATEGY_HEALTH["max_consecutive_losing_months"]:
            weaknesses.append(f"连续亏损{cons_lose}个月")

        # 盈亏比
        if profit_factor < 1.0:
            weaknesses.append(f"盈亏比不足 ({profit_factor:.2f})")
        elif profit_factor > 2.0:
            strengths.append(f"盈亏比优秀 ({profit_factor:.2f})")

        # 判定健康度
        if len(weaknesses) >= 3:
            health = "critical"
        elif len(weaknesses) >= 1:
            health = "warning"
        else:
            health = "healthy"

        # 建议
        if health == "critical":
            recommendation = f"策略 {name} 急需改进: {'; '.join(weaknesses)}"
        elif health == "warning":
            recommendation = f"策略 {name} 需要关注: {'; '.join(weaknesses)}"
        else:
            recommendation = f"策略 {name} 运行良好"

        return StrategyHealthReport(
            strategy_name=name,
            overall_health=health,
            metrics=metrics,
            weaknesses=weaknesses,
            strengths=strengths,
            recommendation=recommendation,
        )

    def _get_builtin_strategy_metrics(self, name: str) -> dict:
        """尝试从 stock-analyzer 获取策略的绩效指标。"""
        try:
            from stock_analyzer.strategies.base import get_strategy
            strategy_cls = get_strategy(name)
            # 尝试获取默认参数和元数据
            params = strategy_cls.default_params() if hasattr(strategy_cls, 'default_params') else {}
            return {
                "name": name,
                "params": params,
                "can_import": True,
                # 如果没有实际回测数据，用占位值
                "annual_return": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "data_available": False,  # 标记为需要实际回测
            }
        except Exception:
            return {"can_import": False, "data_available": False}

    def _get_evolve_strategy_metrics(self, name: str) -> dict:
        """获取进化策略的绩效指标。"""
        strategy_module = name.replace("evolve.", "")
        strategy_file = os.path.join(EVOLVE_ROOT, "strategies", f"{strategy_module}.py")
        if os.path.exists(strategy_file):
            return {
                "source": "evolve",
                "file": strategy_file,
                "data_available": False,  # 需要实际回测
            }
        return {"source": "evolve", "found": False}

    @staticmethod
    def _generate_summary(report: AuditReport) -> str:
        """生成审计摘要。"""
        lines = [
            "=" * 60,
            f"策略审计报告 — {report.timestamp[:10]}",
            "=" * 60,
            f"评估策略数: {report.strategies_assessed}",
            f"健康: {report.healthy_count} | 警告: {report.warning_count} | 严重: {report.critical_count}",
            "",
        ]

        if report.critical_count > 0:
            lines.append("🚨 需要立即处理的严重问题:")
            for w in report.top_weaknesses[:5]:
                if w["health"] == "critical":
                    lines.append(f"  [{w['strategy']}] {w['weakness']}")

        if report.warning_count > 0:
            lines.append("\n⚠️ 需要关注的问题:")
            for w in report.top_weaknesses[:5]:
                if w["health"] == "warning":
                    lines.append(f"  [{w['strategy']}] {w['weakness']}")

        if report.critical_count == 0 and report.warning_count == 0:
            lines.append("✅ 所有策略运行正常，无严重问题。")

        return "\n".join(lines)

    def save_report(self, report: AuditReport) -> str:
        """保存审计报告到文件。"""
        from .config import REPORTS_DIR
        os.makedirs(REPORTS_DIR, exist_ok=True)
        filename = f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(REPORTS_DIR, filename)

        data = {
            "timestamp": report.timestamp,
            "strategies_assessed": report.strategies_assessed,
            "healthy_count": report.healthy_count,
            "warning_count": report.warning_count,
            "critical_count": report.critical_count,
            "top_weaknesses": report.top_weaknesses,
            "summary": report.summary,
            "strategy_reports": [
                {
                    "name": sr.strategy_name,
                    "health": sr.overall_health,
                    "metrics": sr.metrics,
                    "weaknesses": sr.weaknesses,
                    "strengths": sr.strengths,
                }
                for sr in report.strategy_reports
            ],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath


def run_audit() -> AuditReport:
    """便捷函数：运行策略审计。"""
    auditor = StrategyAuditor()
    return auditor.run_audit()


def find_weaknesses(state: EvolutionState) -> list[dict]:
    """作为步骤①的一部分：运行审计并更新状态中的弱点列表。

    Returns:
        按严重程度排序的弱点列表
    """
    auditor = StrategyAuditor()
    report = auditor.run_audit()

    # 保存报告
    report_path = auditor.save_report(report)

    # 更新状态
    weaknesses = []
    for w in report.top_weaknesses:
        weaknesses.append({
            "id": f"strat_{w['strategy']}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "type": "strategy_performance",
            "severity": w["health"],
            "description": f"[{w['strategy']}] {w['weakness']}",
            "strategy": w["strategy"],
            "found_at": datetime.now().isoformat(),
            "source_report": report_path,
            "status": "open",
        })

    state.last_audit_run = datetime.now().isoformat()
    state.weaknesses_found.extend(weaknesses)

    return weaknesses
