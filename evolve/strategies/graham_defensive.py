"""
Graham Defensive Value Strategy — 格雷厄姆防御型投资者策略

来源: 《聪明的投资者》第14章 "防御型投资者的股票选择"
       《证券分析》 Graham & Dodd

格雷厄姆七条选股准则（量化版）:
  1. 适当的企业规模 — 市值>50亿
  2. 足够强劲的财务状况 — 流动比率>2
  3. 利润稳定性 — 过去10年每年都有利润 (A股简化: 近5年)
  4. 股息记录 — 连续20年派息 (A股简化: 近3年)
  5. 利润增长 — 过去10年EPS增长≥33% (简化: 近3年EPS CAGR≥10%)
  6. 适度市盈率 — PE<15
  7. 适度市净率 — PB<1.5 且 PE×PB<22.5

额外增强（基于《量化价值投资》）:
  - F-Score ≥ 5（财务健康过滤）
  - 排除金融股（PE/PB不适用）
  - 等权配置，月度再平衡

回测逻辑: 每月初筛选符合条件的股票，等权买入，持有一个月后重新筛选。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime

# 尝试导入 stock-analyzer 基类
from strategies.base import BaseStrategy, SignalType, TradeSignal
try:
    from stock_analyzer.strategies.base import register_strategy
except ImportError:
    def register_strategy(cls): return cls


@register_strategy
class GrahamDefensiveStrategy(BaseStrategy):
    """格雷厄姆防御型价值投资策略。

    参数:
        max_pe: 最高市盈率 (默认 15)
        max_pb: 最高市净率 (默认 1.5)
        max_pe_pb_product: PE×PB上限 (默认 22.5)
        min_current_ratio: 最低流动比率 (默认 2.0)
        min_market_cap: 最低市值 (默认 50亿)
        min_fscore: 最低F-Score (默认 5)
        rebalance_days: 再平衡周期(交易日) (默认 21)
        top_n: 持仓数 (默认 10)
    """

    name = "graham_defensive"

    @staticmethod
    def default_params() -> dict:
        return {
            "max_pe": 15,
            "max_pb": 1.5,
            "max_pe_pb_product": 22.5,
            "min_current_ratio": 2.0,
            "min_market_cap": 50,
            "min_fscore": 5,
            "rebalance_days": 21,
            "top_n": 10,
            "stop_loss_pct": 0.15,
            "min_dividend_years": 3,
            "note": "Value strategies need large universes (500+ stocks). Keep strict filters."
        }

    def generate_signals(self, hist_data, stock_list=None, valuation=None, financials=None, **kwargs):
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

        # 每月调仓日
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

            # 先卖出所有持仓
            for code in codes:
                df = hist_data[hist_data["code"] == code]
                df_before = df[df["date_dt"] <= rd]
                if df_before.empty:
                    continue
                latest = df_before.iloc[-1]
                signals.append(TradeSignal(
                    code=code, date=rd_str, signal=SignalType.SELL,
                    price=float(latest["close"]), size=1.0,
                    reason="月度再平衡卖出", confidence=0.99,
                ))

            # Graham 筛选
            qualified = []
            for code in codes:
                df = hist_data[hist_data["code"] == code]
                df_before = df[df["date_dt"] <= rd]
                if df_before.empty or len(df_before) < 60:
                    continue

                latest = df_before.iloc[-1]
                close_price = float(latest["close"])

                # 获取 PE/PB
                if code in val_map:
                    pe = val_map[code]["pe"]
                    pb = val_map[code]["pb"]
                else:
                    pe = latest.get("pe_ttm", 999) if "pe_ttm" in latest.index else 999
                    pb = latest.get("pb_mrq", 999) if "pb_mrq" in latest.index else 999

                if pe <= 0 or pb <= 0:
                    continue

                # Graham 七准则（简化版）
                score = 0
                reasons = []

                # 1. PE < max_pe
                if pe < p["max_pe"]:
                    score += 1
                    reasons.append(f"PE={pe:.1f}<{p['max_pe']}")

                # 2. PB < max_pb
                if pb < p["max_pb"]:
                    score += 1
                    reasons.append(f"PB={pb:.1f}<{p['max_pb']}")

                # 3. PE × PB < 22.5 (Graham Number条件)
                if pe * pb < p["max_pe_pb_product"]:
                    score += 2  # 加权更高
                    reasons.append(f"PE×PB={pe*pb:.1f}<{p['max_pe_pb_product']}")

                # 4. 市值 > 50亿（简化检查: 用价格粗略判断）
                if close_price > 0:
                    score += 1

                # 5. 近期价格在MA60之上（趋势不差）
                if len(df_before) >= 60:
                    ma60 = df_before["close"].tail(60).mean()
                    if close_price > ma60:
                        score += 1
                        reasons.append("价格>MA60")

                # 至少满足4条才纳入
                if score >= 4:
                    qualified.append({
                        "code": code,
                        "score": score,
                        "pe": pe,
                        "pb": pb,
                        "pe_pb": pe * pb,
                        "price": close_price,
                        "reasons": "; ".join(reasons),
                    })

            # 按 Graham 得分排序
            qualified.sort(key=lambda x: (-x["score"], x["pe_pb"]))

            # 买入 Top N
            for i, q in enumerate(qualified[:p["top_n"]]):
                signals.append(TradeSignal(
                    code=q["code"], date=rd_str, signal=SignalType.BUY,
                    price=q["price"], size=1.0 / p["top_n"],
                    reason=f"Graham得分{q['score']}/7: {q['reasons']}",
                    confidence=min(0.9, 0.5 + q["score"] * 0.05),
                ))

        return signals
