"""
知识缺口扫描 — 对比知识库(100本书/GitHub/Skills) vs 系统现有能力，找到缺失。

步骤① FIND WEAKNESS 的第三个维度。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .config import REPORTS_DIR
from .knowledge_base import KnowledgeBase


@dataclass
class GapReport:
    """知识缺口报告。"""
    timestamp: str
    total_gaps: int
    high_priority: list[dict] = None   # 高优先级：有明确可编码规则
    medium_priority: list[dict] = None  # 中优先级：有框架但需适配
    low_priority: list[dict] = None     # 低优先级：定性框架
    summary: str = ""

    def __post_init__(self):
        self.high_priority = self.high_priority or []
        self.medium_priority = self.medium_priority or []
        self.low_priority = self.low_priority or []


class GapScanner:
    """知识缺口扫描器。

    对比三个知识源 vs 系统现有能力:
      1. 100本经典投资书籍 (from KnowledgeBase)
      2. GitHub顶级量化项目 (from inspiration_scanner 缓存)
      3. Claude Code技能市场

    用法:
        scanner = GapScanner()
        gaps = scanner.scan(existing_strategies=["trend", "momentum", ...])
        for g in gaps.high_priority:
            print(f"缺: {g['name']} from {g['source']}")
    """

    # 系统现有策略能力描述
    CAPABILITY_MAP = {
        "trend": "趋势跟踪",
        "momentum": "动量策略",
        "mean_reversion": "均值回归",
        "grid": "网格交易",
        "rotation": "板块轮动",
        "high_dividend": "高股息防御",
        "etf_rotation": "ETF轮动",
        "regime_adaptive": "市场状态自适应",
        "volume_price": "量价分析",
        "swing_trend": "波段趋势",
        "pca": "PCA选股",
        "multi_factor": "多因子选股",
        "bollinger": "布林带策略",
    }

    def __init__(self):
        self.kb = KnowledgeBase()
        self.kb.load()

    def scan(self, existing_strategies: list[str] | None = None,
             external_repos: list[dict] | None = None,
             skill_market: list[dict] | None = None) -> GapReport:
        """执行全维度知识缺口扫描。

        Args:
            existing_strategies: 系统现有策略名称列表
            external_repos: GitHub项目列表 [{name, description, features}]
            skill_market: 技能市场列表 [{name, description, features}]

        Returns:
            GapReport 按优先级分三档
        """
        existing = existing_strategies or list(self.CAPABILITY_MAP.keys())
        report = GapReport(
            timestamp=datetime.now().isoformat(),
            total_gaps=0,
        )

        # 源1: 100本书知识库
        book_gaps = self.kb.find_gaps(existing)
        for bg in book_gaps:
            if bg.get("difficulty") == "beginner":
                report.high_priority.append({
                    "source": f"书籍《{bg['book']}》({bg['author']})",
                    "name": bg["framework"],
                    "description": bg["description"],
                    "rules": bg.get("rules", []),
                    "category": bg.get("category", ""),
                    "gap_type": "quantifiable_strategy",
                })
            elif bg.get("difficulty") == "intermediate":
                report.medium_priority.append({
                    "source": f"书籍《{bg['book']}》({bg['author']})",
                    "name": bg["framework"],
                    "description": bg["description"],
                    "rules": bg.get("rules", []),
                    "category": bg.get("category", ""),
                    "gap_type": "adaptable_framework",
                })
            else:
                report.low_priority.append({
                    "source": f"书籍《{bg['book']}》({bg['author']})",
                    "name": bg["framework"],
                    "description": bg["description"],
                    "category": bg.get("category", ""),
                    "gap_type": "qualitative_framework",
                })

        # 源2: GitHub项目
        if external_repos:
            repo_gaps = self._scan_github_gaps(external_repos, existing)
            report.high_priority.extend([g for g in repo_gaps if g["gap_type"] == "missing_module"])
            report.medium_priority.extend([g for g in repo_gaps if g["gap_type"] == "enhancement"])

        # 源3: 技能市场
        if skill_market:
            skill_gaps = self._scan_skill_gaps(skill_market, existing)
            report.high_priority.extend([g for g in skill_gaps if g["gap_type"] == "missing_skill"])
            report.medium_priority.extend([g for g in skill_gaps if g["gap_type"] == "partial_coverage"])

        report.total_gaps = len(report.high_priority) + len(report.medium_priority) + len(report.low_priority)
        report.summary = self._generate_summary(report)
        return report

    def _scan_github_gaps(self, repos: list[dict], existing: list[str]) -> list[dict]:
        """扫描GitHub项目中我们缺失的能力。"""
        gaps = []
        known_features = {
            "backtest": "回测引擎",
            "multi_agent": "多智能体架构",
            "llm": "LLM增强分析",
            "factor_mining": "自动因子挖掘",
            "market_simulation": "市场仿真/数字孪生",
            "real_time_trading": "实盘交易接口",
            "options": "期权策略",
            "high_frequency": "高频交易",
            "sentiment": "情绪分析",
            "risk_management": "风险管理",
            "portfolio_optimization": "组合优化",
        }

        for repo in repos:
            features = repo.get("features", [])
            description = repo.get("description", "")
            name = repo.get("name", "")

            for feat_key, feat_cn in known_features.items():
                if feat_key in description.lower() or any(feat_key in f.lower() for f in features):
                    # 检查我们是否有这个能力
                    has_it = self._check_capability(feat_key, existing)
                    if not has_it:
                        gaps.append({
                            "source": f"GitHub: {name}",
                            "name": feat_cn,
                            "description": description,
                            "reference_repo": name,
                            "gap_type": "missing_module",
                        })
        return gaps

    def _scan_skill_gaps(self, skills: list[dict], existing: list[str]) -> list[dict]:
        """扫描技能市场中我们缺失的能力。"""
        gaps = []
        for skill in skills:
            name = skill.get("name", "")
            features = skill.get("features", [])
            # 检查是否已有类似能力
            has_it = any(
                name.lower() in s.lower() or any(f.lower() in s.lower() for f in features)
                for s in existing
            )
            if not has_it:
                gaps.append({
                    "source": f"Skill Market: {name}",
                    "name": name,
                    "description": skill.get("description", ""),
                    "features": features,
                    "gap_type": "missing_skill" if skill.get("is_critical") else "partial_coverage",
                })
        return gaps

    def _check_capability(self, feature: str, existing: list[str]) -> bool:
        """检查系统是否已有某项能力。"""
        feature_lower = feature.lower()
        strategy_lower = [s.lower() for s in existing]
        return any(feature_lower in s for s in strategy_lower)

    @staticmethod
    def _generate_summary(report: GapReport) -> str:
        lines = [
            "=" * 60,
            f"知识缺口扫描 — {report.timestamp[:10]}",
            "=" * 60,
            f"总缺口数: {report.total_gaps}",
            f"高优先级(可编码): {len(report.high_priority)}",
            f"中优先级(需适配): {len(report.medium_priority)}",
            f"低优先级(定性): {len(report.low_priority)}",
            "",
        ]
        if report.high_priority:
            lines.append("🔴 高优先级 — 可直接实现:")
            for g in report.high_priority[:5]:
                lines.append(f"  [{g['source']}] {g['name']}")
        if report.medium_priority:
            lines.append("\n🟡 中优先级 — 需要适配:")
            for g in report.medium_priority[:5]:
                lines.append(f"  [{g['source']}] {g['name']}")
        return "\n".join(lines)

    def save_report(self, report: GapReport) -> str:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        filepath = os.path.join(REPORTS_DIR, f"gap_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        data = {
            "timestamp": report.timestamp,
            "total_gaps": report.total_gaps,
            "high_priority": report.high_priority,
            "medium_priority": report.medium_priority,
            "low_priority": report.low_priority,
            "summary": report.summary,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath
