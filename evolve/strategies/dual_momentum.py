"""
Dual Momentum Strategy — 双动量策略

来源: 《双动量投资》(Dual Momentum Investing) Gary Antonacci
       academic papers by Gary Antonacci

核心思想:
  两种动量结合——绝对动量(不买下跌的) + 相对动量(买涨得最好的)

三层决策:
  1. 绝对动量过滤: 过去12个月收益必须 > 无风险利率(T-bills)，否则持有现金
  2. 相对动量排名: 在通过过滤的标的中，选过去12个月收益最高的
  3. 风险资产选择: 如果所有风险资产都不满足绝对动量 → 持有债券/现金

A股适配:
  - 无风险利率 ≈ 1年期国债收益率(~2.5%)
  - 风险资产 = 宽基指数(300/500/创业板) + 行业ETF
  - 月度调仓
  - 只看价格动量，不需要基本面数据

这是最简单的、历史上表现最稳健的策略之一。

回测逻辑:
  - 对每只股票计算12个月收益率
  - 只买入 12月收益 > 无风险利率 的股票
  - 从中选择收益最高的N只
  - 月度调仓
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.base import BaseStrategy, SignalType, TradeSignal
try:
    from stock_analyzer.strategies.base import register_strategy
except ImportError:
    def register_strategy(cls): return cls


@register_strategy
class DualMomentumStrategy(BaseStrategy):
    """双动量策略。

    绝对动量(趋势过滤) + 相对动量(选最强)

    参数:
        lookback_months: 动量回溯月数 (默认 12)
        risk_free_rate: 无风险利率% (默认 2.5)
        top_n: 持仓数 (默认 3, 集中持仓)
        rebalance_days: 调仓周期 (默认 21)
        min_momentum: 最低绝对动量阈值 (默认 > 无风险利率)
        volatility_filter: 是否过滤高波动股票 (默认 True)
    """

    name = "dual_momentum"

    @staticmethod
    def default_params() -> dict:
        return {
            "lookback_months": 6,   # Reduced for limited data
            "risk_free_rate": 2.5,
            "top_n": 3,
            "rebalance_days": 21,
            "min_momentum": 0,
            "volatility_filter": False,  # Disabled for small universe
            "max_volatility": 50,
            "use_equal_weight": True,
            "min_data_days": 60,  # Minimum data needed
        }

    def generate_signals(self, hist_data, stock_list=None, **kwargs):
        p = self.params
        signals = []

        if hist_data is None or hist_data.empty:
            return signals

        if stock_list is None or stock_list.empty:
            codes = sorted(hist_data["code"].unique())
            stock_list = pd.DataFrame({"code": codes, "name": codes})

        codes = stock_list["code"].tolist()
        hist_data = hist_data.copy()
        hist_data["date_dt"] = pd.to_datetime(hist_data["date"])
        all_dates = sorted(hist_data["date_dt"].unique())

        lookback_days = p["lookback_months"] * 21
        if len(all_dates) < lookback_days + p["rebalance_days"]:
            return signals

        rebalance_dates = [all_dates[i] for i in range(lookback_days, len(all_dates), p["rebalance_days"])]
        min_momentum = p["min_momentum"] if p["min_momentum"] > 0 else p["risk_free_rate"]

        # Track current positions to avoid unnecessary sells
        current_holds = set()

        for rd in rebalance_dates:
            rd_str = rd.strftime("%Y-%m-%d")

            # 计算每只股票的动量和波动率
            momentum_scores = []
            for code in codes:
                df = hist_data[hist_data["code"] == code]
                df_before = df[df["date_dt"] <= rd]
                if df_before.empty or len(df_before) < lookback_days:
                    continue

                # 绝对动量: 12个月收益 (如果数据不足用可用数据)
                lookback_idx = max(0, len(df_before) - lookback_days)
                price_start = float(df_before.iloc[lookback_idx]["close"])
                price_current = float(df_before.iloc[-1]["close"])

                if price_start <= 0:
                    continue

                momentum_12m = (price_current / price_start - 1) * 100

                # 绝对动量过滤
                if momentum_12m <= min_momentum:
                    continue

                # 波动率过滤
                annual_vol = 0
                if p["volatility_filter"]:
                    recent = df_before.tail(60)
                    if len(recent) >= 20:
                        daily_rets = recent["close"].pct_change().dropna()
                        annual_vol = daily_rets.std() * np.sqrt(252) * 100
                        if annual_vol > p["max_volatility"]:
                            continue

                # 近期动量(3个月)用于排序
                recent_idx = max(0, len(df_before) - 63)
                momentum_3m = (price_current / float(df_before.iloc[recent_idx]["close"]) - 1) * 100

                momentum_scores.append({
                    "code": code,
                    "momentum_12m": momentum_12m,
                    "momentum_3m": momentum_3m,
                    "volatility": annual_vol,
                    "price": price_current,
                })

            # 按综合动量排序 (12M权重0.6 + 3M权重0.4)
            momentum_scores.sort(key=lambda x: x["momentum_12m"] * 0.6 + x["momentum_3m"] * 0.4, reverse=True)

            # 确定新的持仓
            n_buy = min(p["top_n"], len(momentum_scores))
            new_holds = set(m["code"] for m in momentum_scores[:n_buy])

            # 只卖出不再持有的
            for code in list(current_holds):
                if code not in new_holds:
                    df = hist_data[hist_data["code"] == code]
                    df_before = df[df["date_dt"] <= rd]
                    if not df_before.empty:
                        signals.append(TradeSignal(
                            code=code, date=rd_str, signal=SignalType.SELL,
                            price=float(df_before.iloc[-1]["close"]), size=1.0,
                            reason="动量排名下降，调出", confidence=0.8,
                        ))

            # 买入新进 Top N 的
            for i in range(n_buy):
                m = momentum_scores[i]
                if m["code"] in current_holds:
                    continue  # Already holding
                size = 1.0 / n_buy if p["use_equal_weight"] else (n_buy - i) / sum(range(1, n_buy + 1))
                signals.append(TradeSignal(
                    code=m["code"], date=rd_str, signal=SignalType.BUY,
                    price=m["price"], size=size,
                    reason=f"DualMomentum Rank#{i+1} 12M={m['momentum_12m']:.1f}% 3M={m['momentum_3m']:.1f}%",
                    confidence=min(0.85, 0.5 + abs(m["momentum_12m"]) / 200),
                ))

            current_holds = new_holds

        # 期末清仓
        if current_holds and all_dates:
            last_date = all_dates[-1].strftime("%Y-%m-%d")
            for code in current_holds:
                df = hist_data[hist_data["code"] == code]
                df_before = df[df["date_dt"] <= all_dates[-1]]
                if not df_before.empty:
                    signals.append(TradeSignal(
                        code=code, date=last_date, signal=SignalType.SELL,
                        price=float(df_before.iloc[-1]["close"]), size=1.0,
                        reason="期末清仓", confidence=0.99,
                    ))

        return signals
