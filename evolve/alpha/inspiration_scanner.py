"""
外部灵感扫描 — 从互联网/GitHub/学术论文/雪球大V持续吸收新知识。

步骤① FIND WEAKNESS 的第六个维度。
每周自动扫描外部信息源，将高价值发现转化为知识缺口或改进建议。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .config import INSPIRATION, REPORTS_DIR


@dataclass
class InspirationItem:
    """单条外部灵感。"""
    source: str          # github / arxiv / xueqiu / skill_market
    title: str
    url: str = ""
    summary: str = ""
    relevance: str = ""  # high / medium / low
    actionable: bool = False
    suggested_action: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class InspirationReport:
    """灵感扫描报告。"""
    timestamp: str
    total_items: int
    high_relevance: int = 0
    actionable_items: list[InspirationItem] = field(default_factory=list)
    all_items: list[InspirationItem] = field(default_factory=list)
    summary: str = ""


class InspirationScanner:
    """外部灵感扫描器。

    从多个外部源收集最新的量化投资思路:
      1. GitHub trending 量化项目
      2. arXiv q-fin 最新论文
      3. 雪球热帖/大V新观点
      4. Claude Code 技能市场新技能

    注: 实际网络抓取需要通过 WebSearch/WebFetch 工具完成，
    本模块定义了扫描框架和数据模型，具体数据由 orchestrator 传入。

    用法:
        scanner = InspirationScanner()
        # 数据由外部工具注入
        items = [
            InspirationItem(source="github", title="ContestTrade", ...)
        ]
        report = scanner.process(items)
    """

    def __init__(self):
        self.search_queries = INSPIRATION["github_search_queries"]

    def process(self, items: list[InspirationItem]) -> InspirationReport:
        """处理扫描到的灵感，过滤去重，输出结构化报告。

        Args:
            items: 从各渠道收集的原始灵感

        Returns:
            InspirationReport 含优先级排序
        """
        # 去重
        seen = set()
        unique = []
        for item in items:
            key = (item.title.lower(), item.source)
            if key not in seen:
                seen.add(key)
                unique.append(item)

        # 分类排序
        actionable = [i for i in unique if i.actionable and i.relevance == "high"]
        high = [i for i in unique if i.relevance == "high" and not i.actionable]
        medium = [i for i in unique if i.relevance == "medium"]
        low = [i for i in unique if i.relevance == "low"]

        sorted_items = actionable + high + medium + low

        report = InspirationReport(
            timestamp=datetime.now().isoformat(),
            total_items=len(sorted_items),
            high_relevance=len(actionable) + len(high),
            actionable_items=actionable,
            all_items=sorted_items,
            summary=self._generate_summary(sorted_items),
        )
        return report

    @staticmethod
    def create_github_items(repos: list[dict]) -> list[InspirationItem]:
        """将 GitHub 仓库信息转化为灵感条目。"""
        items = []
        for repo in repos:
            actionable = repo.get("has_code", False) and repo.get("stars", 0) > 100
            items.append(InspirationItem(
                source="github",
                title=repo.get("name", ""),
                url=repo.get("url", ""),
                summary=repo.get("description", ""),
                relevance=_star_to_relevance(repo.get("stars", 0)),
                actionable=actionable,
                suggested_action=f"研究 {repo.get('name')} 的实现并评估是否可以集成" if actionable else "",
                tags=repo.get("topics", []),
            ))
        return items

    @staticmethod
    def create_arxiv_items(papers: list[dict]) -> list[InspirationItem]:
        """将 arXiv 论文转化为灵感条目。"""
        items = []
        for paper in papers:
            actionable = paper.get("has_code", False)
            items.append(InspirationItem(
                source="arxiv",
                title=paper.get("title", ""),
                url=paper.get("url", ""),
                summary=paper.get("abstract", "")[:200],
                relevance="high" if paper.get("has_code") else "medium",
                actionable=actionable,
                suggested_action=f"复现论文 {paper.get('title')} 的方法" if actionable else "",
                tags=paper.get("categories", []),
            ))
        return items

    @staticmethod
    def create_xueqiu_items(posts: list[dict]) -> list[InspirationItem]:
        """将雪球帖子转化为灵感条目。"""
        items = []
        for post in posts:
            items.append(InspirationItem(
                source="xueqiu",
                title=post.get("title", ""),
                url=post.get("url", ""),
                summary=post.get("summary", ""),
                relevance=post.get("relevance", "medium"),
                actionable=post.get("has_strategy", False),
                suggested_action=post.get("implementation_hint", ""),
                tags=["xueqiu", post.get("category", "general")],
            ))
        return items

    @staticmethod
    def _generate_summary(items: list[InspirationItem]) -> str:
        lines = [
            "=" * 60,
            f"外部灵感扫描 — {datetime.now().strftime('%Y-%m-%d')}",
            "=" * 60,
            f"收集灵感: {len(items)} 条",
        ]
        actionable = [i for i in items if i.actionable]
        if actionable:
            lines.append(f"\n🚀 可执行的灵感 ({len(actionable)}):")
            for item in actionable[:5]:
                lines.append(f"  [{item.source}] {item.title}")
                lines.append(f"    → {item.suggested_action}")
        return "\n".join(lines)

    def save_report(self, report: InspirationReport) -> str:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        filepath = os.path.join(REPORTS_DIR, f"inspiration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        data = {
            "timestamp": report.timestamp,
            "total_items": report.total_items,
            "high_relevance": report.high_relevance,
            "actionable_items": [
                {"source": i.source, "title": i.title, "action": i.suggested_action}
                for i in report.actionable_items
            ],
            "all_items": [
                {"source": i.source, "title": i.title, "relevance": i.relevance,
                 "actionable": i.actionable, "tags": i.tags}
                for i in report.all_items
            ],
            "summary": report.summary,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath


def _star_to_relevance(stars: int) -> str:
    if stars >= 5000:
        return "high"
    elif stars >= 500:
        return "medium"
    return "low"
