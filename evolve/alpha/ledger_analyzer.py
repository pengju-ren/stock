"""
预测账本分析 — 从历史预测错误中学习，找出决策系统的系统性问题。

步骤① FIND WEAKNESS 的第五个维度。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .config import REPORTS_DIR
from .state import load_ledger


@dataclass
class ErrorPattern:
    """一种反复出现的错误模式。"""
    pattern_name: str
    description: str
    frequency: int
    total_occurrences: int
    avg_loss: float
    root_cause: str
    affected_strategies: list[str]
    recommendation: str


@dataclass
class LedgerAnalysisReport:
    """预测账本分析报告。"""
    timestamp: str
    total_predictions: int
    closed_predictions: int
    win_rate: float
    avg_return: float
    profit_factor: float
    error_patterns: list[ErrorPattern] = field(default_factory=list)
    dimension_breakdown: dict = field(default_factory=dict)
    summary: str = ""


class LedgerAnalyzer:
    """预测账本分析器。

    分析所有历史预测的结果，找出:
      - 哪种类型的预测错误率最高
      - 哪个分析维度(技术/基本/情绪)的误判最多
      - 什么市场状态下决策质量最差
      - 反复出现的错误模式

    用法:
        analyzer = LedgerAnalyzer()
        report = analyzer.analyze()
        for pattern in report.error_patterns:
            print(f"{pattern.pattern_name}: {pattern.recommendation}")
    """

    def analyze(self) -> LedgerAnalysisReport:
        """分析预测账本，输出决策系统的系统性弱点。"""
        ledger = load_ledger()

        report = LedgerAnalysisReport(
            timestamp=datetime.now().isoformat(),
            total_predictions=len(ledger),
            closed_predictions=0,
            win_rate=0.0,
            avg_return=0.0,
            profit_factor=0.0,
        )

        if not ledger:
            report.summary = "预测账本为空，尚无足够数据进行分析。"
            return report

        closed = [e for e in ledger if e.get("status") == "closed"]
        report.closed_predictions = len(closed)

        if not closed:
            report.summary = "尚无已完结的预测，无法计算胜率和错误模式。"
            return report

        # 基础统计
        wins = [e for e in closed if e.get("actual_outcome") == "win"]
        losses = [e for e in closed if e.get("actual_outcome") == "loss"]

        report.win_rate = len(wins) / len(closed) if closed else 0
        report.avg_return = sum(e.get("actual_return", 0) for e in closed) / len(closed)

        total_profit = sum(e.get("actual_return", 0) for e in wins)
        total_loss = abs(sum(e.get("actual_return", 0) for e in losses))
        report.profit_factor = total_profit / total_loss if total_loss > 0 else 99

        # 按维度分析错误
        report.dimension_breakdown = self._analyze_by_dimension(closed)

        # 识别错误模式
        report.error_patterns = self._detect_error_patterns(closed)

        report.summary = self._generate_summary(report)
        return report

    def _analyze_by_dimension(self, closed_predictions: list[dict]) -> dict:
        """按维度分析预测质量。"""
        dims = {}
        for entry in closed_predictions:
            tech = entry.get("technical_score", 0)
            fund = entry.get("fundamental_score", 0)
            sent = entry.get("sentiment_score", 0)
            outcome = entry.get("actual_outcome", "")

            for dim_name, score in [("技术面", tech), ("基本面", fund), ("情绪面", sent)]:
                if dim_name not in dims:
                    dims[dim_name] = {"correct": 0, "total": 0}

                if score > 0:
                    dims[dim_name]["total"] += 1
                    if outcome == "win":
                        dims[dim_name]["correct"] += 1

        # 计算准确率
        for dim in dims.values():
            dim["accuracy"] = dim["correct"] / dim["total"] if dim["total"] > 0 else 0
            dim["error_rate"] = 1 - dim["accuracy"]

        return dims

    def _detect_error_patterns(self, closed_predictions: list[dict]) -> list[ErrorPattern]:
        """识别反复出现的错误模式。"""
        patterns = []
        losses = [e for e in closed_predictions if e.get("actual_outcome") == "loss"]

        if not losses:
            return patterns

        # 模式1: 技术面高分但亏损 → 技术信号不可靠
        tech_high_losses = [
            e for e in losses
            if e.get("technical_score", 0) >= 7 and e.get("fundamental_score", 0) < 6
        ]
        if len(tech_high_losses) >= 3:
            patterns.append(ErrorPattern(
                pattern_name="技术信号误判",
                description="技术面评分高(≥7)但基本面评分低(<6)的预测亏损概率高",
                frequency=len(tech_high_losses),
                total_occurrences=len(closed_predictions),
                avg_loss=sum(e.get("actual_return", 0) for e in tech_high_losses) / max(len(tech_high_losses), 1),
                root_cause="过度依赖技术面信号，忽略基本面风险",
                affected_strategies=list(set(e.get("source_strategy", "unknown") for e in tech_high_losses)),
                recommendation="修改信号生成逻辑：技术评分≥7但基本面<6时，降低仓位至半仓以下",
            ))

        # 模式2: 高置信度亏损 → 过度自信
        high_conf_losses = [
            e for e in losses if e.get("confidence", 0) >= 8
        ]
        if len(high_conf_losses) >= 2:
            patterns.append(ErrorPattern(
                pattern_name="高置信度预测失败",
                description=f"置信度≥8的预测仍有{len(high_conf_losses)}次亏损",
                frequency=len(high_conf_losses),
                total_occurrences=len(closed_predictions),
                avg_loss=sum(e.get("actual_return", 0) for e in high_conf_losses) / max(len(high_conf_losses), 1),
                root_cause="对抗验证不够严格，未能发现关键风险因素",
                affected_strategies=list(set(e.get("source_strategy", "unknown") for e in high_conf_losses)),
                recommendation="加强对抗验证：置信度≥8时必须通过做空逻辑驳斥测试",
            ))

        # 模式3: 止损触发但随后反弹 → 止损设太紧
        stopped_out = [
            e for e in losses
            if "stop" in e.get("review_notes", "").lower()
            or "止损" in e.get("review_notes", "")
        ]
        if len(stopped_out) >= 3:
            patterns.append(ErrorPattern(
                pattern_name="止损设置过紧",
                description="多次触发止损后股价反弹，止损参数可能需要调整",
                frequency=len(stopped_out),
                total_occurrences=len(closed_predictions),
                avg_loss=sum(e.get("actual_return", 0) for e in stopped_out) / max(len(stopped_out), 1),
                root_cause="ATR倍数设置偏低或波动率校准不及时",
                affected_strategies=list(set(e.get("source_strategy", "unknown") for e in stopped_out)),
                recommendation="动态调整止损：高波动环境用ATR×3，低波动环境用ATR×2",
            ))

        return patterns

    @staticmethod
    def _generate_summary(report: LedgerAnalysisReport) -> str:
        lines = [
            "=" * 60,
            f"预测账本分析 — {report.timestamp[:10]}",
            "=" * 60,
            f"总预测: {report.total_predictions} | 已完结: {report.closed_predictions}",
            f"胜率: {report.win_rate:.1%} | 平均收益: {report.avg_return:.1%} | 盈亏比: {report.profit_factor:.2f}",
            "",
        ]

        if report.error_patterns:
            lines.append("🔍 发现的错误模式:")
            for ep in report.error_patterns:
                lines.append(f"  ❌ {ep.pattern_name}")
                lines.append(f"     出现{ep.frequency}次 | 均损{ep.avg_loss:.1%}")
                lines.append(f"     根因: {ep.root_cause}")
                lines.append(f"     建议: {ep.recommendation}")
        else:
            lines.append("✅ 未检测到明显的系统性错误模式。")

        if report.dimension_breakdown:
            lines.append("\n维度准确性:")
            for dim, stats in report.dimension_breakdown.items():
                lines.append(f"  {dim}: {stats.get('accuracy', 0):.1%}")

        return "\n".join(lines)

    def save_report(self, report: LedgerAnalysisReport) -> str:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        filepath = os.path.join(REPORTS_DIR, f"ledger_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        data = {
            "timestamp": report.timestamp,
            "total_predictions": report.total_predictions,
            "closed_predictions": report.closed_predictions,
            "win_rate": report.win_rate,
            "avg_return": report.avg_return,
            "profit_factor": report.profit_factor,
            "error_patterns": [
                {"name": ep.pattern_name, "frequency": ep.frequency,
                 "root_cause": ep.root_cause, "recommendation": ep.recommendation}
                for ep in report.error_patterns
            ],
            "dimension_accuracy": report.dimension_breakdown,
            "summary": report.summary,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath
