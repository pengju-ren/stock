"""
策略构建器 — 步骤② BUILD/FIX 的核心。

根据步骤①发现的弱点，生成改进方案并实施。
支持三种改进模式:
  1. 修复现有策略 (fix)
  2. 新建策略 (build_new)
  3. 调整因子权重 (tune_weights)
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .config import MAX_BUILD_ATTEMPTS, STRATEGIES_DIR, STOCK_ANALYZER_SRC
from .knowledge_base import KnowledgeBase

if STOCK_ANALYZER_SRC not in sys.path:
    sys.path.insert(0, os.path.dirname(STOCK_ANALYZER_SRC))


@dataclass
class BuildPlan:
    """一个改进方案。"""
    id: str
    target_weakness_id: str
    mode: str  # fix / build_new / tune_weights
    goal: str
    approach: str  # 采用的方法论
    referenced_books: list[str]  # 参考的书籍
    referenced_repos: list[str]  # 参考的GitHub项目
    code_changes: list[dict]  # [{file, change_type: new/modify, description}]
    config_changes: dict  # 需要调整的配置参数
    expected_impact: dict  # {metric: expected_change}


@dataclass
class BuildResult:
    """构建结果。"""
    plan: BuildPlan
    success: bool
    files_created: list[str]
    files_modified: list[str]
    errors: list[str]
    next_steps: str


class StrategyBuilder:
    """策略构建器。

    将弱点转化为具体的代码改动。

    用法:
        builder = StrategyBuilder()
        plan = builder.design_plan(weakness)
        result = builder.execute(plan)
    """

    def __init__(self):
        self.kb = KnowledgeBase()
        self.kb.load()

    def design_plan(self, weakness: dict, attempt_count: int = 0) -> BuildPlan:
        """根据弱点设计改进方案。

        Args:
            weakness: 步骤①发现的弱点 {id, type, severity, description, strategy}
            attempt_count: 这是第几次尝试（用于切换方案）

        Returns:
            BuildPlan 包含完整的执行计划
        """
        w_type = weakness.get("type", "")
        w_desc = weakness.get("description", "")
        w_strategy = weakness.get("strategy", "")

        # 搜索知识库中的相关框架
        related_books = self._find_related_knowledge(w_desc)

        plan_id = f"build_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        if w_type == "strategy_performance":
            return self._plan_strategy_fix(plan_id, weakness, related_books, attempt_count)
        elif w_type == "factor_decay":
            return self._plan_factor_fix(plan_id, weakness, related_books)
        elif w_type == "knowledge_gap":
            return self._plan_new_strategy(plan_id, weakness, related_books)
        elif w_type == "regime_change":
            return self._plan_regime_adaptation(plan_id, weakness, related_books)
        else:
            return self._plan_generic(plan_id, weakness, related_books)

    def _plan_strategy_fix(self, plan_id: str, weakness: dict,
                           books: list[str], attempt: int) -> BuildPlan:
        """修复现有策略的方案。"""
        strategy = weakness.get("strategy", "unknown")
        desc = weakness.get("description", "")
        goal = f"修复 {strategy} 策略: {desc}"

        # 根据尝试次数切换方法
        if attempt == 0:
            approach = "参数调优：调整止损/仓位/入场条件参数"
            config_changes = {"stop_loss_multiplier": "adjust ±0.5", "position_size": "reduce 20%"}
        elif attempt == 1:
            approach = "加过滤条件：增加多条件确认，减少假信号"
            config_changes = {"entry_filters": "add 2 more confirmations", "min_confidence": "+1"}
        else:
            approach = "重构策略逻辑：从知识库借鉴替代方法"
            config_changes = {"strategy_overhaul": "replace core signal logic"}

        return BuildPlan(
            id=plan_id, target_weakness_id=weakness.get("id", ""),
            mode="fix", goal=goal, approach=approach,
            referenced_books=books[:3],
            referenced_repos=[],
            code_changes=[{"file": f"strategies/{strategy}.py", "change_type": "modify",
                           "description": approach}],
            config_changes=config_changes,
            expected_impact={"sharpe_ratio": "+0.3", "max_drawdown": "-5%"},
        )

    def _plan_new_strategy(self, plan_id: str, weakness: dict,
                           books: list[str]) -> BuildPlan:
        """新建策略的方案。"""
        name = weakness.get("description", "新策略")
        goal = f"实现新策略: {name}"

        rules = weakness.get("rules", [])
        approach = f"将知识库中的规则转化为策略代码: {'; '.join(rules[:3])}"

        # 生成策略文件名
        strategy_name = name.replace(" ", "_").lower()[:40]

        return BuildPlan(
            id=plan_id, target_weakness_id=weakness.get("id", ""),
            mode="build_new", goal=goal, approach=approach,
            referenced_books=books,
            referenced_repos=[],
            code_changes=[{"file": f"strategies/{strategy_name}.py", "change_type": "new",
                           "description": f"基于 {books[0] if books else '知识库'} 实现"}],
            config_changes={"new_strategy_weight": 0.05},
            expected_impact={"new_alpha_source": "新增一个独立收益来源"},
        )

    def _plan_factor_fix(self, plan_id: str, weakness: dict,
                         books: list[str]) -> BuildPlan:
        """修复因子的方案。"""
        goal = f"修复/替换失效因子: {weakness.get('description', '')}"
        approach = "降低失效因子权重，引入替代因子"
        return BuildPlan(
            id=plan_id, target_weakness_id=weakness.get("id", ""),
            mode="tune_weights", goal=goal, approach=approach,
            referenced_books=books, referenced_repos=[],
            code_changes=[],
            config_changes={"factor_weights": "rebalance — reduce dead + increase improving"},
            expected_impact={"ic_mean": "+0.02", "strategy_sharpe": "+0.2"},
        )

    def _plan_regime_adaptation(self, plan_id: str, weakness: dict,
                                books: list[str]) -> BuildPlan:
        """适应市场状态变化的方案。"""
        goal = f"适应市场状态变化: {weakness.get('description', '')}"
        approach = "调整 regime_adaptive 策略的权重分配"
        return BuildPlan(
            id=plan_id, target_weakness_id=weakness.get("id", ""),
            mode="fix", goal=goal, approach=approach,
            referenced_books=books, referenced_repos=[],
            code_changes=[{"file": "strategies/regime_adaptive.py", "change_type": "modify",
                           "description": "更新子策略权重映射"}],
            config_changes={"regime_weights": "recalibrate based on new regime"},
            expected_impact={"regime_match": "improved", "downside_protection": "+10%"},
        )

    def _plan_generic(self, plan_id: str, weakness: dict,
                      books: list[str]) -> BuildPlan:
        """通用改进方案。"""
        return BuildPlan(
            id=plan_id, target_weakness_id=weakness.get("id", ""),
            mode="fix", goal=f"修复: {weakness.get('description', '')}",
            approach="根据知识库参考进行通用改进",
            referenced_books=books, referenced_repos=[],
            code_changes=[], config_changes={},
            expected_impact={},
        )

    def execute(self, plan: BuildPlan) -> BuildResult:
        """执行构建方案。

        创建或修改 evolve/strategies/ 下的策略文件。
        不会触碰 stock-analyzer 的原始文件。

        Returns:
            BuildResult 包含执行结果
        """
        files_created = []
        files_modified = []
        errors = []

        for change in plan.code_changes:
            filepath = os.path.join(STRATEGIES_DIR, os.path.basename(change["file"]))
            try:
                if change["change_type"] == "new":
                    strategy_code = self._generate_strategy_skeleton(plan, change)
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(strategy_code)
                    files_created.append(filepath)

                elif change["change_type"] == "modify":
                    if os.path.exists(filepath):
                        with open(filepath, "a", encoding="utf-8") as f:
                            f.write(f"\n# [EVOLVE] {datetime.now().strftime('%Y-%m-%d')}: "
                                    f"{plan.goal}\n")
                            f.write(f"# Approach: {plan.approach}\n")
                            if plan.referenced_books:
                                f.write(f"# Reference: {', '.join(plan.referenced_books)}\n")
                        files_modified.append(filepath)
                    else:
                        # File doesn't exist in evolve/ — try to create a new strategy
                        # instead of failing. Based on the weakness info, generate a skeleton.
                        strategy_code = self._generate_strategy_skeleton(plan, change)
                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(strategy_code)
                        files_created.append(filepath)

            except Exception as e:
                errors.append(f"写入 {filepath} 失败: {e}")

        result = BuildResult(
            plan=plan,
            success=len(errors) == 0 and (len(files_created) + len(files_modified) > 0),
            files_created=files_created,
            files_modified=files_modified,
            errors=errors,
            next_steps=f"运行 verifier 验证 {plan.goal}",
        )

        if not result.success and not result.files_created and not result.files_modified:
            result.errors.append("没有产生任何文件变更")

        return result

    def _generate_strategy_skeleton(self, plan: BuildPlan, change: dict) -> str:
        """为新策略生成代码骨架。"""
        strategy_name = os.path.basename(change["file"]).replace(".py", "")

        return f'''"""
{plan.goal}

基于:
{chr(10).join(f"  - {b}" for b in plan.referenced_books) if plan.referenced_books else "  - 知识库搜索"}

方法: {plan.approach}
生成时间: {datetime.now().isoformat()}
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# 参考 stock-analyzer 的基类接口
try:
    from stock_analyzer.strategies.base import (
        BaseStrategy, SignalType, TradeSignal, register_strategy,
    )
    USING_STOCK_ANALYZER = True
except ImportError:
    USING_STOCK_ANALYZER = False
    # 独立运行时的最小基类
    class SignalType:
        BUY = "BUY"
        SELL = "SELL"
        HOLD = "HOLD"

    class TradeSignal:
        def __init__(self, code, date, signal, price=0, size=1, reason="", confidence=0.5):
            self.code = code
            self.date = date
            self.signal = signal
            self.price = price
            self.size = size
            self.reason = reason
            self.confidence = confidence
            self.metadata = {{}}

    class BaseStrategy:
        name = "base"
        params = {{}}

        @staticmethod
        def default_params():
            return {{}}

        def generate_signals(self, hist_data, stock_list=None, **kwargs):
            raise NotImplementedError


@register_strategy if USING_STOCK_ANALYZER else (lambda x: x)
class {strategy_name.title().replace('_', '')}(BaseStrategy):
    """{plan.goal}

    核心逻辑:
    {plan.approach}

    参数:
        lookback_days: 回溯天数 (默认 60)
        min_confidence: 最小置信度 (默认 0.5)
        max_positions: 最大持仓数 (默认 10)
    """

    name = "{strategy_name}"

    @staticmethod
    def default_params() -> dict:
        return {{
            "lookback_days": 60,
            "min_confidence": 0.5,
            "max_positions": 10,
            "stop_loss_atr_multiple": 2.5,
            "take_profit_atr_multiple": 3.0,
        }}

    def generate_signals(
        self,
        hist_data: pd.DataFrame,
        stock_list: pd.DataFrame | None = None,
        **kwargs,
    ) -> list:
        """生成交易信号。

        Args:
            hist_data: [code, date, open, high, low, close, volume]
            stock_list: [code, name, market]

        Returns:
            list[TradeSignal]
        """
        p = self.params
        signals = []

        if hist_data is None or hist_data.empty:
            return signals

        if stock_list is None or stock_list.empty:
            codes = sorted(hist_data["code"].unique())
            stock_list = pd.DataFrame({{"code": codes, "name": codes}})

        codes = stock_list["code"].tolist()

        for code in codes:
            df = hist_data[hist_data["code"] == code].sort_values("date")
            if len(df) < p["lookback_days"]:
                continue

            # TODO: 在此实现具体的策略逻辑
            # 参考: {plan.approach}

        return signals
'''

    def _find_related_knowledge(self, description: str) -> list[str]:
        """在知识库中搜索与弱点相关的书籍和框架。"""
        frameworks = self.kb.search_frameworks(description)
        if not frameworks and "动量" in description:
            frameworks = self.kb.search_frameworks("momentum")
        if not frameworks and "回撤" in description:
            frameworks = self.kb.search_frameworks("risk")

        books = []
        seen = set()
        for fw in frameworks[:5]:
            book = fw.get("book", "")
            if book not in seen:
                books.append(book)
                seen.add(book)
        return books


def design_and_build(weakness: dict, attempt: int = 0) -> BuildResult:
    """便捷函数：设计并执行一个改进。"""
    builder = StrategyBuilder()
    plan = builder.design_plan(weakness, attempt)
    return builder.execute(plan)
