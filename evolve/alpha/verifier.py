"""
验证引擎 — 步骤③ VERIFY 的核心。

对改进后的策略进行三重验证:
  1. 基础回测 (年化/夏普/回撤/胜率/盈亏比)
  2. 滚动窗口验证 (检测过拟合)
  3. 压力测试 (蒙特卡洛 + 极端事件)
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

from .config import VERIFICATION, STRATEGIES_DIR, REPORTS_DIR, STOCK_ANALYZER_SRC

if STOCK_ANALYZER_SRC not in sys.path:
    sys.path.insert(0, os.path.dirname(STOCK_ANALYZER_SRC))


@dataclass
class VerificationResult:
    """策略验证结果。"""
    strategy_name: str
    passed: bool
    metrics: dict[str, Any] = field(default_factory=dict)
    rolling_results: list[dict] = field(default_factory=list)
    stress_test_results: dict = field(default_factory=dict)
    fail_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendation: str = ""


class StrategyVerifier:
    """策略验证器。

    三重验证流程:
      L1: 基础回测 — 年化收益/夏普/最大回撤/胜率/盈亏比 是否达标
      L2: 滚动窗口 — 多个子周期的表现是否一致（检测过拟合）
      L3: 压力测试 — 蒙特卡洛模拟 + 历史极端事件回放

    阈值来自 config.VERIFICATION。

    用法:
        verifier = StrategyVerifier()
        result = verifier.verify("my_strategy", hist_data, strategy_obj)
        if result.passed:
            print("✅ 验证通过")
        else:
            print(f"❌ 验证失败: {result.fail_reasons}")
    """

    def __init__(self):
        self.config = VERIFICATION

    def verify(self, strategy_name: str,
               hist_data: pd.DataFrame | None = None,
               strategy_obj=None,
               benchmark_returns: pd.Series | None = None,
               trades_df: pd.DataFrame | None = None,
               equity_curve: pd.DataFrame | None = None,
               metrics_override: dict | None = None) -> VerificationResult:
        """对策略进行完整的三重验证。

        Args:
            strategy_name: 策略名称
            hist_data: 历史K线数据
            strategy_obj: 策略实例（需要有 backtest 方法或 generate_signals 方法）
            benchmark_returns: 基准收益序列
            trades_df: 交易记录 DataFrame（如果已有）
            equity_curve: 权益曲线 DataFrame（如果已有）
            metrics_override: 手动指定的指标（用于跳过回测直接验证）

        Returns:
            VerificationResult
        """
        result = VerificationResult(strategy_name=strategy_name, passed=True)
        metrics = metrics_override or {}

        # L1: 基础指标验证
        if metrics:
            l1_pass, l1_fails = self._check_basic_metrics(metrics)
        elif strategy_obj and hist_data is not None:
            metrics = self._run_backtest(strategy_obj, hist_data)
            l1_pass, l1_fails = self._check_basic_metrics(metrics)
        else:
            l1_pass = True  # 无数据时跳过
            l1_fails = []

        result.metrics = metrics
        if not l1_pass:
            result.passed = False
            result.fail_reasons.extend(l1_fails)

        # L2: 滚动窗口验证
        if hist_data is not None and strategy_obj is not None:
            rolling = self._rolling_window_validate(strategy_obj, hist_data)
            result.rolling_results = rolling
            l2_pass, l2_fails = self._check_rolling(rolling)
            if not l2_pass:
                result.passed = False
                result.fail_reasons.extend(l2_fails)
        else:
            result.warnings.append("跳过滚动窗口验证（无数据或策略对象）")

        # L3: 压力测试
        if equity_curve is not None and not equity_curve.empty:
            stress = self._stress_test(equity_curve)
            result.stress_test_results = stress
            l3_pass, l3_fails = self._check_stress(stress)
            if not l3_pass:
                result.passed = False
                result.fail_reasons.extend(l3_fails)
        else:
            result.warnings.append("跳过压力测试（无权益曲线数据）")

        # 生成建议
        result.recommendation = self._generate_recommendation(result)
        return result

    def _check_basic_metrics(self, metrics: dict) -> tuple[bool, list[str]]:
        """检查基础指标是否达标。"""
        fails = []
        cfg = self.config

        def _f(v): return float(v) if v is not None else 0.0

        ann_ret = _f(metrics.get("annual_return", 0))
        sharpe = _f(metrics.get("sharpe_ratio", 0))
        max_dd = _f(metrics.get("max_drawdown", 0))
        win_rate = _f(metrics.get("win_rate", 0))
        profit_factor = _f(metrics.get("profit_factor", 0))

        if ann_ret < cfg["min_annual_return_vs_benchmark"] * 100:
            fails.append(f"年化收益 {ann_ret:.1f}% 不达标 (要求>{cfg['min_annual_return_vs_benchmark']*100:.0f}%)")

        if sharpe < cfg["min_sharpe_ratio"]:
            fails.append(f"夏普 {sharpe:.2f} 不达标 (要求>{cfg['min_sharpe_ratio']})")

        if abs(max_dd) > cfg["max_drawdown"] * 100:
            fails.append(f"最大回撤 {abs(max_dd):.1f}% 超标 (要求<{cfg['max_drawdown']*100:.0f}%)")

        if win_rate < cfg["min_win_rate"] * 100:
            fails.append(f"胜率 {win_rate:.1f}% 不达标 (要求>{cfg['min_win_rate']*100:.0f}%)")

        if profit_factor < cfg["min_profit_factor"]:
            fails.append(f"盈亏比 {profit_factor:.2f} 不达标 (要求>{cfg['min_profit_factor']})")

        return len(fails) == 0, fails

    def _check_rolling(self, rolling: list[dict]) -> tuple[bool, list[str]]:
        """检查滚动窗口验证结果。"""
        fails = []
        cfg = self.config

        if not rolling:
            return True, []

        positive_windows = sum(1 for r in rolling if r.get("total_return", 0) > 0)
        required = cfg["rolling_positive_required"]

        if positive_windows < required:
            fails.append(f"滚动窗口正收益: {positive_windows}/{len(rolling)} "
                         f"(要求≥{required})")

        # 检查各窗口的稳定性
        returns = [r.get("total_return", 0) for r in rolling]
        if returns:
            mean_ret = np.mean(returns)
            std_ret = np.std(returns)
            if std_ret > abs(mean_ret) * 2:
                fails.append(f"滚动窗口收益波动过大 (std={std_ret:.1f}% vs mean={mean_ret:.1f}%)")

        return len(fails) == 0, fails

    def _check_stress(self, stress: dict) -> tuple[bool, list[str]]:
        """检查压力测试结果。"""
        fails = []

        var_95 = stress.get("monte_carlo_var95", 0)
        if var_95 < -0.30:  # 95% VaR 日损失超过30%
            fails.append(f"蒙特卡洛 VaR95 过大 ({var_95:.1%})")

        max_dd_stress = stress.get("max_drawdown_stress", 0)
        if abs(max_dd_stress) > 0.40:  # 极端事件回撤超过40%
            fails.append(f"极端事件最大回撤超标 ({abs(max_dd_stress):.1%})")

        return len(fails) == 0, fails

    def _run_backtest(self, strategy_obj, hist_data: pd.DataFrame) -> dict:
        """运行基础回测。"""
        try:
            if hasattr(strategy_obj, 'backtest'):
                bt_result = strategy_obj.backtest(hist_data)
                return {
                    "annual_return": bt_result.annual_return if hasattr(bt_result, 'annual_return') else 0,
                    "sharpe_ratio": bt_result.sharpe_ratio if hasattr(bt_result, 'sharpe_ratio') else 0,
                    "max_drawdown": bt_result.max_drawdown if hasattr(bt_result, 'max_drawdown') else 0,
                    "win_rate": bt_result.win_rate if hasattr(bt_result, 'win_rate') else 0,
                    "profit_factor": bt_result.profit_factor if hasattr(bt_result, 'profit_factor') else 0,
                    "total_return": bt_result.total_return if hasattr(bt_result, 'total_return') else 0,
                    "total_trades": bt_result.total_trades if hasattr(bt_result, 'total_trades') else 0,
                }
        except Exception as e:
            return {"error": str(e)}

        # 回退：只用信号数量做基础评估
        try:
            signals = strategy_obj.generate_signals(hist_data)
            buy_count = sum(1 for s in signals if hasattr(s, 'signal') and str(s.signal) == 'BUY')
            return {
                "signals_generated": len(signals),
                "buy_signals": buy_count,
                "note": "无回测引擎，仅统计信号数量",
            }
        except Exception as e:
            return {"error": str(e)}

    def _rolling_window_validate(self, strategy_obj,
                                  hist_data: pd.DataFrame) -> list[dict]:
        """滚动窗口验证。"""
        cfg = self.config
        n_windows = cfg["rolling_window_count"]
        window_days = cfg["rolling_window_months"] * 21  # 每月约21个交易日

        if hist_data.empty:
            return []

        # 按日期排序
        if "date" in hist_data.columns:
            dates = sorted(hist_data["date"].unique())
        else:
            return []

        if len(dates) < window_days * 2:
            return []

        results = []
        step = max(1, (len(dates) - window_days) // n_windows)

        for i in range(n_windows):
            start_idx = i * step
            end_idx = min(start_idx + window_days, len(dates))
            if end_idx - start_idx < 60:  # 至少需要60个交易日
                continue

            window_dates = dates[start_idx:end_idx]
            window_data = hist_data[hist_data["date"].isin(window_dates)]

            try:
                window_metrics = self._run_backtest(strategy_obj, window_data)
                results.append({
                    "window": i + 1,
                    "start_date": str(window_dates[0])[:10],
                    "end_date": str(window_dates[-1])[:10],
                    **window_metrics,
                })
            except Exception:
                continue

        return results

    def _stress_test(self, equity_curve: pd.DataFrame) -> dict:
        """压力测试。"""
        result = {}

        if equity_curve.empty or "equity" not in equity_curve.columns:
            return result

        equity = equity_curve["equity"].values

        # 蒙特卡洛模拟
        if len(equity) >= 2:
            daily_returns = np.diff(equity) / equity[:-1]
            if len(daily_returns) > 0 and daily_returns.std() > 0:
                mc_runs = self.config["monte_carlo_runs"]
                simulated_returns = np.random.choice(
                    daily_returns,
                    size=(mc_runs, min(252, len(daily_returns))),
                    replace=True,
                )
                mc_cumulative = np.cumprod(1 + simulated_returns, axis=1)
                mc_final = mc_cumulative[:, -1] - 1

                result["monte_carlo_var95"] = round(float(np.percentile(mc_final, 5)), 4)
                result["monte_carlo_mean"] = round(float(np.mean(mc_final)), 4)
                result["monte_carlo_worst"] = round(float(np.min(mc_final)), 4)

        # 最大回撤
        if "drawdown" in equity_curve.columns:
            result["max_drawdown_stress"] = round(float(equity_curve["drawdown"].min()), 4)

        return result

    def _generate_recommendation(self, result: VerificationResult) -> str:
        """生成验证建议。"""
        if result.passed:
            return f"✅ {result.strategy_name} 通过全部验证，可以合入系统"
        else:
            return (f"❌ {result.strategy_name} 验证未通过:\n" +
                    "\n".join(f"  - {r}" for r in result.fail_reasons))

    def save_result(self, result: VerificationResult) -> str:
        """保存验证结果。"""
        os.makedirs(REPORTS_DIR, exist_ok=True)
        filepath = os.path.join(REPORTS_DIR, f"verify_{result.strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        data = {
            "strategy": result.strategy_name,
            "passed": result.passed,
            "metrics": result.metrics,
            "rolling_results": result.rolling_results,
            "stress_test": result.stress_test_results,
            "fail_reasons": result.fail_reasons,
            "warnings": result.warnings,
            "recommendation": result.recommendation,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath
