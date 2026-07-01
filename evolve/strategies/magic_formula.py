"""
Greenblatt Magic Formula Strategy — 格林布拉特神奇公式

来源: 《股市稳赚》(The Little Book That Still Beats the Market) Joel Greenblatt

核心思想:
  同时买入"好公司"(高ROC)和"便宜股票"(高盈利收益率)的交集

两个排名:
  1. 盈利收益率排名 = EBIT / EV (越高越好 → 越便宜)
  2. 资本回报率排名 = EBIT / (净营运资本 + 净固定资产) (越高越好 → 越优秀)

综合排名 = 盈利收益率排名 + ROC排名
买入综合排名最高的 20-30 只股票，持有一年后卖出

A股适配:
  - EBIT ≈ 营业利润
  - EV ≈ 市值 + 总负债 - 现金
  - ROC ≈ EBIT / (总资产 - 流动负债 + 短期负债)
  - 简化版: 盈利收益率 = 1/PE, ROC = ROE
  - 排除金融和公共事业

回测逻辑: 月度调仓，从候选池选综合排名最高的5只
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
class MagicFormulaStrategy(BaseStrategy):
    """格林布拉特神奇公式策略。

    核心: 买好公司(高ROE) + 买便宜(低PE)的交集

    参数:
        top_n: 持仓数 (默认 5)
        rebalance_days: 再平衡周期 (默认 21)
        min_roe: 最低ROE过滤 (默认 10%)
        max_pe: 最高PE过滤 (默认 30)
        exclude_financials: 排除金融股 (默认 True)
    """

    name = "magic_formula"

    @staticmethod
    def default_params() -> dict:
        return {
            "top_n": 5,
            "rebalance_days": 21,
            "min_roe": 10,  # %
            "max_pe": 30,
            "exclude_financials": True,
            "stop_loss_pct": 0.12,
            "ranking_weight_ey": 0.5,  # 盈利收益率权重
            "ranking_weight_roc": 0.5,  # ROC权重
        }

    def generate_signals(self, hist_data, stock_list=None, valuation=None, **kwargs):
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

        if len(all_dates) < p["rebalance_days"]:
            return signals

        rebalance_dates = [all_dates[i] for i in range(0, len(all_dates), p["rebalance_days"])]

        # 估值数据
        val_map = {}
        if valuation is not None and not valuation.empty:
            for _, row in valuation.iterrows():
                val_map[row["code"]] = {
                    "pe": row.get("pe_ttm", 999),
                    "pb": row.get("pb_mrq", 999),
                    "price": row.get("price", 0),
                }

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
                    reason="Magic Formula再平衡", confidence=0.99,
                ))

            # 评分
            rankings = []
            for code in codes:
                df = hist_data[hist_data["code"] == code]
                df_before = df[df["date_dt"] <= rd]
                if df_before.empty or len(df_before) < 60:
                    continue

                latest = df_before.iloc[-1]
                close_price = float(latest["close"])

                # PE → 盈利收益率
                if code in val_map:
                    pe = val_map[code]["pe"]
                else:
                    pe = latest.get("pe_ttm", 999) if "pe_ttm" in latest.index else 999

                if pe <= 0 or pe > p["max_pe"]:
                    continue

                earnings_yield = (1.0 / pe) * 100  # 盈利收益率 %

                # ROE → ROC (简化)
                # 从历史数据推算: ROE ≈ (close_change / close) 的粗略估计
                # 更好的做法是使用financials数据
                # 这里用价格动量和PE的比值作为ROC的代理
                if len(df_before) >= 252:
                    price_1y_ago = float(df_before.iloc[-252]["close"])
                    price_change = (close_price / price_1y_ago - 1) * 100
                else:
                    price_change = (close_price / float(df_before.iloc[0]["close"]) - 1) * 100

                # 简单代理: ROC = 盈利收益率 + 价格变化的一部分
                proxy_roc = earnings_yield + max(0, price_change * 0.3)

                rankings.append({
                    "code": code,
                    "earnings_yield": earnings_yield,
                    "proxy_roc": proxy_roc,
                    "pe": pe,
                    "price": close_price,
                    "price_change_1y": price_change,
                })

            if not rankings:
                continue

            # 排名: 盈利收益率(高=好) + ROC代理(高=好)
            rankings.sort(key=lambda x: x["earnings_yield"], reverse=True)
            for i, r in enumerate(rankings):
                r["ey_rank"] = i + 1

            rankings.sort(key=lambda x: x["proxy_roc"], reverse=True)
            for i, r in enumerate(rankings):
                r["roc_rank"] = i + 1

            # 综合排名
            for r in rankings:
                r["composite_rank"] = (
                    r["ey_rank"] * p["ranking_weight_ey"] +
                    r["roc_rank"] * p["ranking_weight_roc"]
                )

            rankings.sort(key=lambda x: x["composite_rank"])

            # 买入 Top N
            for i, r in enumerate(rankings[:p["top_n"]]):
                signals.append(TradeSignal(
                    code=r["code"], date=rd_str, signal=SignalType.BUY,
                    price=r["price"], size=1.0 / p["top_n"],
                    reason=f"MagicFormula Rank#{i+1} EY={r['earnings_yield']:.1f}% PE={r['pe']:.1f}",
                    confidence=min(0.85, 0.5 + (len(rankings) - r["composite_rank"]) / len(rankings) * 0.35),
                ))

        return signals
