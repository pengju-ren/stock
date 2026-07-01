"""
因子健康检测 — 监控每个因子的预测能力(IC)，发现衰减和失效。

步骤① FIND WEAKNESS 的第二个维度。
计算滚动IC、检测衰减趋势、标记低共线性因子组。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from .config import FACTOR_HEALTH, REPORTS_DIR


@dataclass
class FactorHealth:
    """单个因子的健康状态。"""
    name: str
    category: str  # trend / momentum / volatility / volume / fundamental / etc.
    current_ic: float
    rolling_ic_mean: float
    rolling_ic_std: float
    ic_t_stat: float
    trend: str  # stable / declining / improving / dead
    status: str  # healthy / warning / dead
    recommendation: str = ""


@dataclass
class FactorHealthReport:
    """完整的因子健康报告。"""
    timestamp: str
    factors_assessed: int
    healthy_count: int = 0
    warning_count: int = 0
    dead_count: int = 0
    factor_details: list[FactorHealth] = field(default_factory=list)
    high_correlation_pairs: list[dict] = field(default_factory=list)
    summary: str = ""


class FactorDoctor:
    """因子健康医生。

    监控所有因子的:
      - Information Coefficient (IC): 因子值与未来收益的相关性
      - IC 衰减: IC 是否从显著变为不显著
      - 共线性: 哪些因子高度相关（可精简）

    用法:
        doctor = FactorDoctor()
        report = doctor.checkup(returns_df, factor_df)
        for dead in report.get_dead_factors():
            print(f"废弃因子: {dead.name}, IC={dead.current_ic:.4f}")
    """

    # 已知的因子列表（从 stock-analyzer config 和实际代码中提取）
    KNOWN_FACTORS = {
        # 技术面 — 趋势
        "ma_alignment": "trend",
        "ma_cross": "trend",
        "adx_trend": "trend",
        # 技术面 — 动量
        "rsi_signal": "momentum",
        "macd_signal": "momentum",
        "cci_signal": "momentum",
        "willr_signal": "momentum",
        "mfi_signal": "momentum",
        "roc_signal": "momentum",
        # 技术面 — 波动率
        "bollinger_signal": "volatility",
        "atr_signal": "volatility",
        "keltner_signal": "volatility",
        "stddev_signal": "volatility",
        # 技术面 — 成交量
        "volume_signal": "volume",
        "obv_signal": "volume",
        "adosc_signal": "volume",
        "cmf_signal": "volume",
        # 技术面 — 形态
        "pattern_bullish": "pattern",
        "pattern_bearish": "pattern",
        "consecutive_days": "pattern",
        # 基本面
        "pe_rank": "fundamental",
        "pb_rank": "fundamental",
        "roe": "fundamental",
        "profit_growth": "fundamental",
        "revenue_growth": "fundamental",
        "debt_ratio": "fundamental",
        "cashflow_quality": "fundamental",
        "revenue_qoq": "fundamental",
        "profit_qoq": "fundamental",
        "margin_trend": "fundamental",
        "dupont": "fundamental",
        # 资金面
        "main_flow_5d": "capital_flow",
        "main_flow_20d": "capital_flow",
        "big_order_ratio": "capital_flow",
        "volume_price_match": "capital_flow",
        "north_flow": "capital_flow",
    }

    def __init__(self):
        self.factors = dict(self.KNOWN_FACTORS)

    def checkup(self, returns: pd.DataFrame | None = None,
                factor_values: pd.DataFrame | None = None,
                historical_ic: dict | None = None) -> FactorHealthReport:
        """执行因子健康检查。

        Args:
            returns: 股票收益数据 [date, code, forward_return]
            factor_values: 因子值 [date, code, factor1, factor2, ...]
            historical_ic: 历史IC序列 {factor_name: [ic_values]}

        Returns:
            FactorHealthReport
        """
        report = FactorHealthReport(
            timestamp=datetime.now().isoformat(),
            factors_assessed=len(self.factors),
        )

        for factor_name, category in self.factors.items():
            health = self._assess_factor(
                factor_name, category,
                returns, factor_values, historical_ic,
            )
            report.factor_details.append(health)

            if health.status == "healthy":
                report.healthy_count += 1
            elif health.status == "warning":
                report.warning_count += 1
            else:
                report.dead_count += 1

        # 检测高相关性因子对
        if factor_values is not None and not factor_values.empty:
            report.high_correlation_pairs = self._detect_collinearity(factor_values)

        report.summary = self._generate_summary(report)
        return report

    def _assess_factor(self, name: str, category: str,
                       returns: pd.DataFrame | None,
                       factor_values: pd.DataFrame | None,
                       hist_ic: dict | None) -> FactorHealth:
        """评估单个因子。"""
        current_ic = 0.0
        rolling_mean = 0.0
        rolling_std = 0.0
        t_stat = 0.0
        ic_series = []

        # 从历史IC获取
        if hist_ic and name in hist_ic:
            ic_series = hist_ic[name]
            if len(ic_series) > 0:
                current_ic = ic_series[-1] if isinstance(ic_series, list) else float(ic_series)
                rolling_mean = np.mean(ic_series[-FACTOR_HEALTH["ic_rolling_window"]:])
                rolling_std = np.std(ic_series[-FACTOR_HEALTH["ic_rolling_window"]:])
                if rolling_std > 0:
                    t_stat = abs(rolling_mean) / (rolling_std / np.sqrt(min(len(ic_series), FACTOR_HEALTH["ic_rolling_window"])))

        # 从实时数据计算（如果有）
        if returns is not None and factor_values is not None and name in factor_values.columns:
            try:
                current_ic = self._compute_ic(factor_values[name], returns)
            except Exception:
                pass

        # --- 判定逻辑 ---
        abs_ic = abs(current_ic)
        abs_rolling = abs(rolling_mean)

        # 趋势判断
        if len(ic_series) >= 40:
            first_half = np.mean(ic_series[:len(ic_series)//2])
            second_half = np.mean(ic_series[len(ic_series)//2:])
            if second_half > first_half + FACTOR_HEALTH["ic_decline_threshold"]:
                trend = "improving"
            elif second_half < first_half - FACTOR_HEALTH["ic_decline_threshold"]:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        # 状态判断
        if abs_rolling < FACTOR_HEALTH["min_ic_absolute"]:
            status = "dead"
        elif trend == "declining" and abs_rolling < FACTOR_HEALTH["min_ic_absolute"] * 2:
            status = "warning"
        elif t_stat < 1.5:
            status = "warning"
        else:
            status = "healthy"

        # 建议
        if status == "dead":
            recommendation = f"因子 {name} 已失效（IC={current_ic:.4f}），建议移除或替换"
        elif status == "warning":
            recommendation = f"因子 {name} 在衰减（IC={current_ic:.4f}, 趋势={trend}），持续观察"
        else:
            recommendation = f"因子 {name} 正常运行"

        return FactorHealth(
            name=name, category=category,
            current_ic=round(current_ic, 4),
            rolling_ic_mean=round(rolling_mean, 4),
            rolling_ic_std=round(rolling_std, 4),
            ic_t_stat=round(t_stat, 2),
            trend=trend, status=status,
            recommendation=recommendation,
        )

    @staticmethod
    def _compute_ic(factor_series: pd.Series, returns: pd.Series) -> float:
        """计算单个因子的 Information Coefficient (Rank IC)。"""
        combined = pd.DataFrame({"factor": factor_series, "return": returns}).dropna()
        if len(combined) < 30:
            return 0.0
        return combined["factor"].corr(combined["return"], method="spearman")

    def _detect_collinearity(self, factor_values: pd.DataFrame) -> list[dict]:
        """检测高相关性的因子对。"""
        high_pairs = []
        factor_cols = [c for c in factor_values.columns if c in self.factors]
        if len(factor_cols) < 2:
            return high_pairs

        corr = factor_values[factor_cols].corr()
        for i in range(len(factor_cols)):
            for j in range(i + 1, len(factor_cols)):
                if abs(corr.iloc[i, j]) > FACTOR_HEALTH["max_correlation_between_factors"]:
                    high_pairs.append({
                        "factor_a": factor_cols[i],
                        "factor_b": factor_cols[j],
                        "correlation": round(corr.iloc[i, j], 3),
                    })

        high_pairs.sort(key=lambda x: abs(x["correlation"]), reverse=True)
        return high_pairs

    @staticmethod
    def _generate_summary(report: FactorHealthReport) -> str:
        lines = [
            "=" * 60,
            f"因子健康报告 — {report.timestamp[:10]}",
            "=" * 60,
            f"评估因子数: {report.factors_assessed}",
            f"健康: {report.healthy_count} | 预警: {report.warning_count} | 失效: {report.dead_count}",
            "",
        ]
        if report.dead_count > 0:
            lines.append("💀 已失效因子:")
            for f in report.factor_details:
                if f.status == "dead":
                    lines.append(f"  {f.name} (IC={f.current_ic:.4f}, {f.category})")
        if report.warning_count > 0:
            lines.append("\n⚠️ 在衰减的因子:")
            for f in report.factor_details:
                if f.status == "warning":
                    lines.append(f"  {f.name} (IC={f.current_ic:.4f}, {f.trend})")
        if report.high_correlation_pairs:
            lines.append("\n🔗 高相关性因子对 (可精简):")
            for pair in report.high_correlation_pairs[:5]:
                lines.append(f"  {pair['factor_a']} <-> {pair['factor_b']}: r={pair['correlation']:.3f}")
        return "\n".join(lines)

    def save_report(self, report: FactorHealthReport) -> str:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        filepath = os.path.join(REPORTS_DIR, f"factor_health_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        data = {
            "timestamp": report.timestamp,
            "factors_assessed": report.factors_assessed,
            "healthy": report.healthy_count,
            "warning": report.warning_count,
            "dead": report.dead_count,
            "factor_details": [
                {"name": f.name, "category": f.category, "ic": f.current_ic,
                 "status": f.status, "trend": f.trend}
                for f in report.factor_details
            ],
            "collinear_pairs": report.high_correlation_pairs,
            "summary": report.summary,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath
