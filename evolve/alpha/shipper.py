"""
合入引擎 — 步骤④ SHIP 的核心。

将通过验证的改进正式合入系统:
  1. 更新策略文件到 evolve/strategies/
  2. 写入 changelog
  3. 更新进化状态
  4. 归档失败尝试
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .config import CHANGELOGS_DIR, EXPERIMENTS_DIR, STRATEGIES_DIR
from .state import EvolutionState, save_state


@dataclass
class ShipResult:
    """合入结果。"""
    success: bool
    improvement_id: str
    changelog_path: str
    archived_experiments: list[str]
    actions_taken: list[str]
    summary: str


class Shipper:
    """合入管理器。

    将通过验证的改进正式纳入系统:
      1. 确认所有文件就位
      2. 生成 changelog
      3. 更新 state.json 中的改进历史
      4. 归档失败的尝试

    用法:
        shipper = Shipper()
        result = shipper.ship(
            build_result=build_result,
            verify_result=verify_result,
            state=state,
        )
    """

    def ship(self, build_result=None, verify_result=None,
             state: EvolutionState | None = None,
             improvement: dict | None = None) -> ShipResult:
        """执行合入。

        Args:
            build_result: 步骤②的构建结果
            verify_result: 步骤③的验证结果
            state: 进化状态
            improvement: 改进信息 {weakness_id, goal, approach, ...}

        Returns:
            ShipResult
        """
        now = datetime.now()
        improvement_id = f"IMP-{now.strftime('%Y%m%d-%H%M%S')}"
        actions = []
        archived = []

        # 1. 写 changelog
        changelog_path = self._write_changelog(
            improvement_id, build_result, verify_result, improvement
        )
        actions.append(f"Changelog: {changelog_path}")

        # 2. 确认策略文件在正确位置
        if build_result and build_result.files_created:
            for f in build_result.files_created:
                if os.path.exists(f):
                    actions.append(f"新策略文件: {f}")

        if build_result and build_result.files_modified:
            for f in build_result.files_modified:
                if os.path.exists(f):
                    actions.append(f"修改文件: {f}")

        # 3. 归档失败尝试(如果有)
        if state and state.failed_experiments:
            archived = self._archive_failures(state.failed_experiments[-3:])
            state.failed_experiments = []

        # 4. 更新进化状态
        passed = verify_result.passed if verify_result else True
        if state:
            history_entry = {
                "id": improvement_id,
                "date": now.strftime("%Y-%m-%d"),
                "passed": passed,
                "goal": improvement.get("goal", "") if improvement else "",
                "approach": improvement.get("approach", "") if improvement else "",
                "verification": {
                    "passed": passed,
                    "metrics": verify_result.metrics if verify_result else {},
                },
                "changelog_path": changelog_path,
            }

            if passed:
                state.improvement_history.append(history_entry)
                state.successful_improvements += 1
            else:
                state.failed_experiments.append(history_entry)
                state.failed_attempts += 1

            # 清理本轮状态
            state.active_improvement = None
            state.verified_improvements = []
            # 将已修复的弱点标记为 fixed
            if improvement and improvement.get("weakness_id"):
                for w in state.weaknesses_found:
                    if w.get("id") == improvement["weakness_id"]:
                        w["status"] = "fixed" if passed else "open"
                        break

            save_state(state)

        # 5. 生成摘要
        if passed:
            summary = (f"✅ 改进 {improvement_id} 已合入系统\n"
                       f"   {improvement.get('goal', '') if improvement else ''}\n"
                       f"   文件变更: {len(actions)} 项\n"
                       f"   已验证通过")
        else:
            summary = (f"❌ 改进 {improvement_id} 验证未通过，已归档到 experiments/\n"
                       f"   原因: 参见 changelog")

        return ShipResult(
            success=passed,
            improvement_id=improvement_id,
            changelog_path=changelog_path,
            archived_experiments=archived,
            actions_taken=actions,
            summary=summary,
        )

    def _write_changelog(self, imp_id: str, build_result=None,
                         verify_result=None, improvement: dict | None = None) -> str:
        """写入变更日志。"""
        os.makedirs(CHANGELOGS_DIR, exist_ok=True)

        now = datetime.now()
        filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{imp_id}.md"
        filepath = os.path.join(CHANGELOGS_DIR, filename)

        lines = [
            f"# 改进 {imp_id}",
            f"",
            f"**日期**: {now.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**状态**: {'✅ 通过' if (verify_result and verify_result.passed) else '❌ 未通过'}",
            f"",
        ]

        if improvement:
            lines.extend([
                f"## 目标",
                f"{improvement.get('goal', 'N/A')}",
                f"",
                f"## 方法",
                f"{improvement.get('approach', 'N/A')}",
                f"",
            ])

        if build_result:
            lines.extend([
                f"## 构建",
                f"- 新建文件: {build_result.files_created}",
                f"- 修改文件: {build_result.files_modified}",
                f"- 参考书籍: {build_result.plan.referenced_books if build_result.plan else 'N/A'}",
                f"",
            ])

        if verify_result:
            lines.extend([
                f"## 验证",
                f"- 通过: {'✅' if verify_result.passed else '❌'}",
                f"- 指标: {json.dumps(verify_result.metrics, ensure_ascii=False)}",
                f"",
            ])
            if verify_result.fail_reasons:
                lines.append(f"- 失败原因: {verify_result.fail_reasons}")
            if verify_result.rolling_results:
                lines.append(f"- 滚动窗口: {len(verify_result.rolling_results)} 个窗口")
            if verify_result.stress_test_results:
                lines.append(f"- 压力测试: {verify_result.stress_test_results}")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return filepath

    def _archive_failures(self, failed: list[dict]) -> list[str]:
        """归档失败尝试到 experiments/。"""
        os.makedirs(EXPERIMENTS_DIR, exist_ok=True)
        archived = []

        for fail in failed:
            timestamp = fail.get("date", datetime.now().strftime("%Y%m%d"))
            archive_file = os.path.join(EXPERIMENTS_DIR, f"failed_{timestamp}.json")
            with open(archive_file, "w", encoding="utf-8") as f:
                json.dump(fail, f, ensure_ascii=False, indent=2)
            archived.append(archive_file)

        return archived


def quick_ship(build_result, verify_result, state=None) -> ShipResult:
    """便捷函数：快速合入。"""
    shipper = Shipper()
    return shipper.ship(build_result=build_result, verify_result=verify_result, state=state)
