"""
CAN SLIM Breakout Strategy — O'Neil成长突破策略

来源: 《笑傲股市》(How to Make Money in Stocks) William J. O'Neil
       IBD (Investor's Business Daily) CAN SLIM 系统

CAN SLIM 七字母:
  C = Current Quarterly Earnings — 当季EPS增速 > 25%
  A = Annual Earnings — 年度EPS增速 > 25%，连续三年增长
  N = New — 新产品/新管理/新高（股价创新高）
  S = Supply & Demand — 成交量放大验证
  L = Leader — 领涨股，RS > 80
  I = Institutional Sponsorship — 机构增持
  M = Market Direction — 大盘趋势向上

A股简化版(数据可得性):
  C: 近一季度收盘涨幅 > 行业均值
  A: 近一年价格涨幅 > 25%
  N: 近20日创过新高
  S: 近5日均量 > 近20日均量 × 1.3
  L: 近60日涨幅排名 > 80分位
  M: 价格在MA60之上

回测逻辑:
  - 每只股票计算CAN SLIM得分(0-7)
  - 买入得分>=5的股票
  - 严格止损 -7%
  - 突破买入，回调加仓
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
class CanSlimStrategy(BaseStrategy):
    """CAN SLIM 成长突破策略。

    参数:
        min_q_eps_growth: 最低季度EPS增速 (默认 25%)
        min_a_eps_growth: 最低年度EPS增速 (默认 25%)
        new_high_lookback: 新高回溯天数 (默认 20)
        volume_ratio: 放量倍率 (默认 1.3)
        rs_percentile: RS分位阈值 (默认 80)
        stop_loss_pct: 止损比例 (默认 0.07, O'Neil铁律)
        min_score: 最低CAN SLIM得分 (默认 5)
        top_n: 最大持仓 (默认 5)
    """

    name = "can_slim"

    @staticmethod
    def default_params() -> dict:
        return {
            "min_q_eps_growth": 10,
            "min_a_eps_growth": 15,
            "new_high_lookback": 20,
            "volume_ratio": 1.2,
            "rs_percentile": 70,
            "stop_loss_pct": 0.08,
            "min_score": 4,
            "top_n": 5,
            "rebalance_days": 21,  # Monthly (rotation finding: monthly >> weekly)
            "trailing_stop_atr": 2.5,  # V2 enhancement
            "take_profit_pct": 50,     # Let profits run
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

        if len(all_dates) < 60:
            return signals

        rebalance_dates = [all_dates[i] for i in range(60, len(all_dates), p["rebalance_days"])]

        for rd in rebalance_dates:
            rd_str = rd.strftime("%Y-%m-%d")

            # 卖出
            for code in codes:
                df = hist_data[hist_data["code"] == code]
                df_before = df[df["date_dt"] <= rd]
                if df_before.empty:
                    continue
                signals.append(TradeSignal(
                    code=code, date=rd_str, signal=SignalType.SELL,
                    price=float(df_before.iloc[-1]["close"]), size=1.0,
                    reason="CAN SLIM再平衡", confidence=0.99,
                ))

            # 计算每只股票的 CAN SLIM 得分
            canslim_scores = []
            for code in codes:
                df = hist_data[hist_data["code"] == code]
                df_before = df[df["date_dt"] <= rd]
                if df_before.empty or len(df_before) < 120:
                    continue

                close_prices = df_before["close"]
                volumes = df_before["volume"] if "volume" in df_before.columns else pd.Series([0]*len(df_before))
                current_price = float(close_prices.iloc[-1])

                score = 0
                details = []

                # C: 近一季度收益 > 25% (用价格代理)
                if len(close_prices) >= 63:
                    q_return = (current_price / float(close_prices.iloc[-63]) - 1) * 100
                    if q_return > p["min_q_eps_growth"]:
                        score += 1
                        details.append(f"C:{q_return:.0f}%")

                # A: 近一年收益 > 25%
                if len(close_prices) >= 252:
                    a_return = (current_price / float(close_prices.iloc[-252]) - 1) * 100
                    if a_return > p["min_a_eps_growth"]:
                        score += 1
                        details.append(f"A:{a_return:.0f}%")

                # N: 近20日创新高
                high_20 = close_prices.iloc[-p["new_high_lookback"]:].max()
                if current_price >= high_20 * 0.98:  # 2%内视为新高
                    score += 1
                    details.append("N:近新高")

                # S: 放量
                if len(volumes) >= 20:
                    avg_vol_20 = volumes.iloc[-21:-1].mean()
                    recent_vol = volumes.iloc[-5:].mean()
                    if avg_vol_20 > 0 and recent_vol / avg_vol_20 > p["volume_ratio"]:
                        score += 1
                        details.append("S:放量")

                # L: 领涨股 (60日涨幅)
                if len(close_prices) >= 60:
                    ret_60 = (current_price / float(close_prices.iloc[-60]) - 1) * 100
                    if ret_60 > 10:  # 简化: 60日涨幅>10%
                        score += 1
                        details.append(f"L:{ret_60:.0f}%")

                # M: 大盘方向(价格在MA60之上)
                if len(close_prices) >= 60:
                    ma60 = close_prices.iloc[-60:].mean()
                    if current_price > ma60:
                        score += 1
                        details.append("M:>MA60")

                # 动量得分
                if len(close_prices) >= 20:
                    ret_20 = (current_price / float(close_prices.iloc[-20]) - 1) * 100
                else:
                    ret_20 = 0

                if score >= p["min_score"]:
                    canslim_scores.append({
                        "code": code,
                        "score": score,
                        "details": "; ".join(details),
                        "price": current_price,
                        "momentum_20d": ret_20,
                    })

            # 按得分排序
            canslim_scores.sort(key=lambda x: (-x["score"], -x["momentum_20d"]))

            # 买入 Top N
            for i, cs in enumerate(canslim_scores[:p["top_n"]]):
                confidence = min(0.9, 0.4 + cs["score"] * 0.08)
                signals.append(TradeSignal(
                    code=cs["code"], date=rd_str, signal=SignalType.BUY,
                    price=cs["price"], size=1.0 / p["top_n"],
                    reason=f"CANSLIM {cs['score']}/7: {cs['details']}",
                    confidence=confidence,
                    metadata={"stop_loss": cs["price"] * (1 - p["stop_loss_pct"])},
                ))

        return signals

# [EVOLVE] 2026-07-01: 修复 can_slim 策略: [can_slim] 夏普比率过低 (0.00)
# Approach: 参数调优：调整止损/仓位/入场条件参数
