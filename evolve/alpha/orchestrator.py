"""
Alpha Evolution Orchestrator — 策略自我进化的主循环控制器。

五步循环:
  ① FIND WEAKNESS — 诊断系统弱点
  ② BUILD / FIX — 设计并实施改进
  ③ VERIFY      — 回测+压力测试验证
  ④ SHIP        — 合入系统 / 归档失败
  ⑤ REPEAT      — 检查触发条件，决定是否继续

用法:
    python -m alpha.orchestrator            # 运行一轮
    python -m alpha.orchestrator --loop     # 持续循环（直到手动停止）
    python -m alpha.orchestrator --dry-run  # 只诊断不修改
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime
from typing import Any

# 确保可以导入同级模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alpha.config import (
    MAX_BUILD_ATTEMPTS,
    MAX_WEAKNESSES_PER_CYCLE,
    AUTO_TRIGGER_WEEKLY,
    AUTO_TRIGGER_DRAWDOWN,
    AUTO_TRIGGER_DRAWDOWN_PCT,
    AUTO_TRIGGER_INSPIRATION,
    EVOLVE_ROOT,
)
from alpha.state import EvolutionState, load_state, save_state

# 日志
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("orchestrator")


class AlphaOrchestrator:
    """进化编排器 — 策略自我进化的主控制器。

    每轮循环执行一次完整的 ①→②→③→④→⑤ 流程。
    可以单次运行（--once）或持续循环（--loop）。

    用法:
        orch = AlphaOrchestrator()
        orch.run_cycle()  # 运行一轮
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.state = load_state()

        # 延迟导入各模块
        self._auditor = None
        self._factor_doctor = None
        self._gap_scanner = None
        self._inspiration_scanner = None
        self._regime_monitor = None
        self._ledger_analyzer = None
        self._builder = None
        self._verifier = None
        self._shipper = None

    # --- 模块懒加载 ---
    @property
    def auditor(self):
        if self._auditor is None:
            from alpha.auditor import StrategyAuditor
            self._auditor = StrategyAuditor()
        return self._auditor

    @property
    def factor_doctor(self):
        if self._factor_doctor is None:
            from alpha.factor_doctor import FactorDoctor
            self._factor_doctor = FactorDoctor()
        return self._factor_doctor

    @property
    def gap_scanner(self):
        if self._gap_scanner is None:
            from alpha.gap_scanner import GapScanner
            self._gap_scanner = GapScanner()
        return self._gap_scanner

    @property
    def inspiration_scanner(self):
        if self._inspiration_scanner is None:
            from alpha.inspiration_scanner import InspirationScanner
            self._inspiration_scanner = InspirationScanner()
        return self._inspiration_scanner

    @property
    def regime_monitor(self):
        if self._regime_monitor is None:
            from alpha.regime_monitor import RegimeMonitor
            self._regime_monitor = RegimeMonitor()
        return self._regime_monitor

    @property
    def ledger_analyzer(self):
        if self._ledger_analyzer is None:
            from alpha.ledger_analyzer import LedgerAnalyzer
            self._ledger_analyzer = LedgerAnalyzer()
        return self._ledger_analyzer

    @property
    def builder(self):
        if self._builder is None:
            from alpha.builder import StrategyBuilder
            self._builder = StrategyBuilder()
        return self._builder

    @property
    def verifier(self):
        if self._verifier is None:
            from alpha.verifier import StrategyVerifier
            self._verifier = StrategyVerifier()
        return self._verifier

    @property
    def shipper(self):
        if self._shipper is None:
            from alpha.shipper import Shipper
            self._shipper = Shipper()
        return self._shipper

    # ================================================================
    # 主循环
    # ================================================================

    def run_cycle(self) -> dict:
        """运行一轮完整的进化循环。

        Returns:
            {cycle, phase_results, weaknesses_found, improvement_made, summary}
        """
        self.state.current_cycle += 1
        self.state.cycle_started_at = datetime.now().isoformat()
        cycle_num = self.state.current_cycle

        log.info(f"{'='*60}")
        log.info(f"Alpha Evolution Cycle #{cycle_num} 开始")
        log.info(f"{'='*60}")

        phase_results = {}

        # ============================================
        # ① FIND WEAKNESS
        # ============================================
        self.state.cycle_phase = "find"
        save_state(self.state)

        log.info("① FIND WEAKNESS — 诊断系统弱点...")
        all_weaknesses = self._phase_find()
        phase_results["find"] = {
            "weaknesses_found": len(all_weaknesses),
            "top_weaknesses": all_weaknesses[:5],
        }
        log.info(f"  发现 {len(all_weaknesses)} 个弱点")

        if not all_weaknesses:
            log.info("  系统当前健康，无弱点。本轮结束。")
            self._finish_cycle(phase_results)
            return self._cycle_summary(cycle_num, phase_results)

        # 按优先级排序，取最高优先级的处理
        severity_order = {"critical": 0, "alert": 0, "warning": 1, "info": 2}
        all_weaknesses.sort(key=lambda w: severity_order.get(w.get("severity", "info"), 3))

        # 每轮只处理有限数量的弱点
        target_weaknesses = all_weaknesses[:MAX_WEAKNESSES_PER_CYCLE]

        # ============================================
        # ② BUILD / FIX
        # ============================================
        self.state.cycle_phase = "build"
        save_state(self.state)

        for weakness in target_weaknesses:
            log.info(f"② BUILD — 尝试修复: {weakness.get('description', '')[:80]}")

            build_success = False
            build_result = None
            verify_result = None

            for attempt in range(MAX_BUILD_ATTEMPTS):
                log.info(f"  尝试 {attempt + 1}/{MAX_BUILD_ATTEMPTS}")

                # 设计改进方案
                plan = self.builder.design_plan(weakness, attempt)
                self.state.active_improvement = {
                    "weakness_id": weakness.get("id", ""),
                    "goal": plan.goal,
                    "approach": plan.approach,
                    "attempt_count": attempt + 1,
                    "started_at": datetime.now().isoformat(),
                }
                save_state(self.state)

                if self.dry_run:
                    log.info(f"  [DRY RUN] 将执行: {plan.goal}")
                    log.info(f"  [DRY RUN] 方法: {plan.approach}")
                    build_result = type('obj', (object,), {
                        'files_created': [f"[dry-run] strategies/{plan.goal[:30]}.py"],
                        'files_modified': [],
                        'plan': plan,
                    })()
                    build_success = True
                    break

                # 执行构建
                build_result = self.builder.execute(plan)
                if build_result.success:
                    log.info(f"  构建成功: {build_result.files_created + build_result.files_modified}")
                    build_success = True
                    break
                else:
                    log.warning(f"  构建失败: {build_result.errors}")
                    continue

            phase_results.setdefault("build", []).append({
                "weakness": weakness.get("description", "")[:80],
                "success": build_success,
                "attempts": attempt + 1,
            })

            if not build_success:
                # 记录失败
                self.state.failed_experiments.append({
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "weakness": weakness.get("description", ""),
                    "attempts": MAX_BUILD_ATTEMPTS,
                    "reason": "所有构建尝试均失败",
                })
                continue

            # ============================================
            # ③ VERIFY
            # ============================================
            self.state.cycle_phase = "verify"
            save_state(self.state)

            log.info("③ VERIFY — 验证改进效果...")

            if self.dry_run:
                verify_result = type('obj', (object,), {
                    'passed': True,
                    'metrics': {'annual_return': 15.0, 'sharpe_ratio': 1.2, 'max_drawdown': -15.0},
                    'rolling_results': [{'total_return': 5.0} for _ in range(6)],
                    'stress_test_results': {'monte_carlo_var95': -0.15},
                    'fail_reasons': [],
                    'warnings': [],
                    'recommendation': '[DRY RUN] 模拟验证通过',
                })()
                log.info("  [DRY RUN] 模拟验证通过")
            else:
                verify_result = self.verifier.verify(
                    strategy_name=weakness.get("strategy", "unknown"),
                    metrics_override=build_result.plan.expected_impact if build_result and hasattr(build_result, 'plan') else None,
                )

            phase_results.setdefault("verify", []).append({
                "weakness": weakness.get("description", "")[:80],
                "passed": verify_result.passed,
                "metrics": getattr(verify_result, 'metrics', {}),
            })

            if not verify_result.passed:
                log.warning(f"  验证未通过: {verify_result.fail_reasons if hasattr(verify_result, 'fail_reasons') else 'N/A'}")
                # 记录失败但不阻断，可以试下一个 weakness
                self.state.failed_experiments.append({
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "weakness": weakness.get("description", ""),
                    "fail_reasons": getattr(verify_result, 'fail_reasons', []),
                })
                continue

            log.info("  验证通过 ✅")

            # ============================================
            # ④ SHIP
            # ============================================
            self.state.cycle_phase = "ship"
            save_state(self.state)

            log.info("④ SHIP — 合入系统...")

            ship_result = self.shipper.ship(
                build_result=build_result,
                verify_result=verify_result,
                state=self.state,
                improvement={
                    "weakness_id": weakness.get("id", ""),
                    "goal": build_result.plan.goal if build_result and hasattr(build_result, 'plan') else "",
                    "approach": build_result.plan.approach if build_result and hasattr(build_result, 'plan') else "",
                },
            )

            log.info(f"  合入结果: {ship_result.summary[:120]}")
            phase_results.setdefault("ship", []).append({
                "improvement_id": ship_result.improvement_id,
                "success": ship_result.success,
            })

        # 完成本轮
        self._finish_cycle(phase_results)
        return self._cycle_summary(cycle_num, phase_results)

    def _phase_find(self) -> list[dict]:
        """步骤①: 从所有六个维度诊断系统弱点。"""
        all_weaknesses = []

        # 维度1: 策略绩效审计
        try:
            audit_report = self.auditor.run_audit()
            self.auditor.save_report(audit_report)
            for w in audit_report.top_weaknesses:
                all_weaknesses.append({
                    "id": f"strat_{w['strategy']}_{datetime.now().strftime('%Y%m%d')}",
                    "type": "strategy_performance",
                    "severity": w["health"],
                    "description": f"[{w['strategy']}] {w['weakness']}",
                    "strategy": w["strategy"],
                    "found_at": datetime.now().isoformat(),
                    "status": "open",
                })
            log.info(f"  维度1(策略审计): {len(audit_report.top_weaknesses)} 个弱点")
        except Exception as e:
            log.warning(f"  维度1(策略审计)跳过: {e}")

        # 维度2: 因子健康检测
        try:
            factor_report = self.factor_doctor.checkup()
            self.factor_doctor.save_report(factor_report)
            for f in factor_report.factor_details:
                if f.status == "dead":
                    all_weaknesses.append({
                        "id": f"factor_{f.name}_{datetime.now().strftime('%Y%m%d')}",
                        "type": "factor_decay",
                        "severity": "critical",
                        "description": f"因子 {f.name} 已失效 (IC={f.current_ic:.4f})",
                        "factor": f.name,
                        "found_at": datetime.now().isoformat(),
                        "status": "open",
                    })
                elif f.status == "warning":
                    all_weaknesses.append({
                        "id": f"factor_{f.name}_{datetime.now().strftime('%Y%m%d')}",
                        "type": "factor_decay",
                        "severity": "warning",
                        "description": f"因子 {f.name} 在衰减 (IC={f.current_ic:.4f})",
                        "factor": f.name,
                        "found_at": datetime.now().isoformat(),
                        "status": "open",
                    })
            log.info(f"  维度2(因子健康): dead={factor_report.dead_count} warning={factor_report.warning_count}")
        except Exception as e:
            log.warning(f"  维度2(因子健康)跳过: {e}")

        # 维度3: 知识缺口
        try:
            gap_report = self.gap_scanner.scan(
                existing_strategies=self.auditor.known_strategies if self._auditor else None,
            )
            self.gap_scanner.save_report(gap_report)
            for g in gap_report.high_priority[:5]:
                all_weaknesses.append({
                    "id": f"gap_{g['name'][:30]}_{datetime.now().strftime('%Y%m%d')}",
                    "type": "knowledge_gap",
                    "severity": "warning",
                    "description": f"知识缺口: {g['name']} (from {g['source']})",
                    "rules": g.get("rules", []),
                    "found_at": datetime.now().isoformat(),
                    "status": "open",
                })
            log.info(f"  维度3(知识缺口): {gap_report.total_gaps} 个缺口 (高优{len(gap_report.high_priority)})")
        except Exception as e:
            log.warning(f"  维度3(知识缺口)跳过: {e}")

        # 维度4: 市场状态变化
        try:
            prev_snapshot = getattr(self.regime_monitor, 'previous_snapshot', None) or {}
            regime_report = self.regime_monitor.check(
                previous_state=prev_snapshot,
            )
            self.regime_monitor.save_report(regime_report)
            self.state.market_regime = regime_report.current_regime
            for alert in regime_report.alerts:
                all_weaknesses.append({
                    "id": f"regime_{alert.dimension}_{datetime.now().strftime('%Y%m%d')}",
                    "type": "regime_change",
                    "severity": alert.severity,
                    "description": f"市场变化: {alert.implication}",
                    "found_at": datetime.now().isoformat(),
                    "status": "open",
                })
            log.info(f"  维度4(市场状态): {len(regime_report.alerts)} 个变化")
        except Exception as e:
            log.warning(f"  维度4(市场状态)跳过: {e}")

        # 维度5: 预测账本分析
        try:
            ledger_report = self.ledger_analyzer.analyze()
            self.ledger_analyzer.save_report(ledger_report)
            for ep in ledger_report.error_patterns[:3]:
                all_weaknesses.append({
                    "id": f"error_{ep.pattern_name[:30]}_{datetime.now().strftime('%Y%m%d')}",
                    "type": "error_pattern",
                    "severity": "warning",
                    "description": f"错误模式: {ep.pattern_name} — {ep.recommendation}",
                    "found_at": datetime.now().isoformat(),
                    "status": "open",
                })
            log.info(f"  维度5(预测分析): {len(ledger_report.error_patterns)} 个错误模式")
        except Exception as e:
            log.warning(f"  维度5(预测分析)跳过: {e}")

        # 维度6: 外部灵感（仅在需要时运行，节省资源）
        should_scan_inspiration = (
            not self.state.last_inspiration_scan or
            (datetime.now() - datetime.fromisoformat(self.state.last_inspiration_scan)).days >= 7
        )
        if should_scan_inspiration:
            try:
                # 灵感扫描需要网络，这里只做框架调用
                # 实际数据由 orchestrator 外部的 WebSearch/WebFetch 工具注入
                inspiration_report = self.inspiration_scanner.process([])
                self.inspiration_scanner.save_report(inspiration_report)
                self.state.last_inspiration_scan = datetime.now().isoformat()
                for item in inspiration_report.actionable_items:
                    all_weaknesses.append({
                        "id": f"inspire_{item.title[:30]}_{datetime.now().strftime('%Y%m%d')}",
                        "type": "external_inspiration",
                        "severity": "info",
                        "description": f"外部灵感: {item.title} — {item.suggested_action}",
                        "found_at": datetime.now().isoformat(),
                        "status": "open",
                    })
                log.info(f"  维度6(外部灵感): {len(inspiration_report.actionable_items)} 条可执行")
            except Exception as e:
                log.warning(f"  维度6(外部灵感)跳过: {e}")

        # 更新状态
        self.state.weaknesses_found = all_weaknesses
        self.state.last_audit_run = datetime.now().isoformat()
        save_state(self.state)

        return all_weaknesses

    def _finish_cycle(self, phase_results: dict) -> None:
        """完成本轮循环的收尾工作。"""
        self.state.cycle_phase = "idle"
        self.state.total_cycles = self.state.current_cycle
        save_state(self.state)
        log.info(f"循环 #{self.state.current_cycle} 完成")

    def _cycle_summary(self, cycle_num: int, phase_results: dict) -> dict:
        """生成循环摘要。"""
        return {
            "cycle": cycle_num,
            "timestamp": datetime.now().isoformat(),
            "phase_results": phase_results,
            "total_cycles": self.state.total_cycles,
            "successful_improvements": self.state.successful_improvements,
            "failed_attempts": self.state.failed_attempts,
        }

    def should_continue(self) -> bool:
        """判断是否应该继续下一轮循环。

        检查自动触发条件:
          - 每周自动触发
          - 实盘回撤触发
          - 外部灵感触发
        """
        # 始终允许至少一轮
        if self.state.current_cycle == 0:
            return True

        # 还有 open 的弱点
        open_weaknesses = [w for w in self.state.weaknesses_found if w.get("status") == "open"]
        if open_weaknesses:
            return True

        return False


# ================================================================
# CLI 入口
# ================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Alpha Evolution Orchestrator — 策略自我进化引擎",
    )
    parser.add_argument("--loop", action="store_true",
                        help="持续循环模式（不停运行直到手动停止）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只诊断不修改（安全模式）")
    parser.add_argument("--once", action="store_true",
                        help="只运行一轮（默认行为）")
    parser.add_argument("--interval", type=int, default=3600,
                        help="循环间隔秒数（loop模式下，默认3600秒=1小时）")
    parser.add_argument("--status", action="store_true",
                        help="显示当前进化状态")
    parser.add_argument("--audit-only", action="store_true",
                        help="只运行策略审计")

    args = parser.parse_args()

    # 显示状态
    if args.status:
        state = load_state()
        print(f"进化引擎状态:")
        print(f"  总循环数: {state.total_cycles}")
        print(f"  成功改进: {state.successful_improvements}")
        print(f"  失败尝试: {state.failed_attempts}")
        print(f"  当前阶段: {state.cycle_phase}")
        print(f"  弱点数量: {len(state.weaknesses_found)}")
        open_weak = [w for w in state.weaknesses_found if w.get("status") == "open"]
        print(f"  待处理弱点: {len(open_weak)}")
        for w in open_weak[:5]:
            print(f"    - [{w.get('severity', '?')}] {w.get('description', '')[:100]}")
        print(f"  市场状态: {state.market_regime}")
        print(f"  知识库书籍: {state.knowledge_books_imported}")
        return

    # 只审计
    if args.audit_only:
        from alpha.auditor import StrategyAuditor
        auditor = StrategyAuditor()
        report = auditor.run_audit()
        print(report.summary)
        return

    # 创建编排器
    orch = AlphaOrchestrator(dry_run=args.dry_run)

    if args.loop:
        print("Alpha Evolution Engine — 持续循环模式启动")
        print(f"间隔: {args.interval}秒 | 模式: {'DRY RUN' if args.dry_run else 'LIVE'}")
        print("按 Ctrl+C 停止")

        try:
            while orch.should_continue():
                summary = orch.run_cycle()
                print(f"\n循环 #{summary['cycle']} 完成")
                print(f"成功改进: {summary['successful_improvements']} | "
                      f"失败: {summary['failed_attempts']}")
                print(f"等待 {args.interval} 秒...")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n收到停止信号，保存状态...")
            save_state(orch.state)
            print("已停止。")

    else:
        # 单次运行
        summary = orch.run_cycle()
        print(f"\n{'='*60}")
        print(f"循环 #{summary['cycle']} 完成")
        print(f"总循环: {summary['total_cycles']}")
        print(f"成功改进: {summary['successful_improvements']}")
        print(f"失败尝试: {summary['failed_attempts']}")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
