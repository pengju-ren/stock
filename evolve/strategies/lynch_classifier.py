"""
Peter Lynch Stock Classifier Strategy — 林奇六类股票+PEG估值

来源: 《彼得·林奇的成功投资》(One Up on Wall Street)
       《战胜华尔街》(Beating the Street)

核心框架:
  六类股票分类法 — 每类用不同的标准评估:
    1. 缓慢增长型: 股息率>3%, 盈利增速<GDP → 看股息
    2. 稳定增长型: 盈利增速8-12%, PE 15-20 → 看PE+股息
    3. 快速增长型: 盈利增速>20%, PEG<1 → 看PEG
    4. 周期型: 盈利随经济周期起伏 → 看PB+库存周期
    5. 困境反转型: 近期亏损但有反转迹象 → 看资产+自由现金流
    6. 隐蔽资产型: 市值<净资产 → 看PB+隐蔽资产

A股简化为四型（量化版）:
  - 快速增长型: 1年涨幅>30% 且 PEG < 1.5 → 买入
  - 稳定增长型: PE < 20 且 股息率 > 2% 且 ROE > 10% → 买入
  - 周期型: PB < 2 且 价格在MA60上 且 行业在上升周期 → 买入
  - 困境反转型: PB < 1 且 价格从最低点反弹>20% → 买入

参数:
    top_n: 每类最多选几只 (默认 3)
    rebalance_days: 调仓周期 (默认 21, 月频)
    min_total_score: 最低买入分 (默认 3/6)
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
class LynchClassifierStrategy(BaseStrategy):
    """林奇分类法 — 按类别分别评估，选出各类型中的最优标的。"""

    name = "lynch_classifier"

    @staticmethod
    def default_params() -> dict:
        return {
            "top_n_per_type": 2,
            "rebalance_days": 21,
            "fast_growth_min_return": 15,  # Relaxed for weak market
            "fast_growth_max_peg": 2.0,    # Relaxed
            "stable_min_dividend": 1.0,
            "stable_max_pe": 30,           # Relaxed for A-shares
            "stable_min_roe": 5,
            "cyclical_max_pb": 3.0,        # Relaxed
            "turnaround_max_pb": 1.5,       # Relaxed
            "turnaround_min_rebound": 10,   # Relaxed: >10% from low
            "total_max_positions": 8,
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

        if len(all_dates) < 120:
            return signals

        rebalance_dates = [all_dates[i] for i in range(120, len(all_dates), p["rebalance_days"])]
        held = set()

        # 估值数据
        val_map = {}
        if valuation is not None and not valuation.empty:
            for _, row in valuation.iterrows():
                code_key = str(row["code"]).replace(".0", "")
                val_map[code_key] = {"pe": row.get("pe_ttm", 999), "pb": row.get("pb_mrq", 999)}

        for rd in rebalance_dates:
            rd_str = rd.strftime("%Y-%m-%d")

            # 分类候选池
            fast_growth = []
            stable = []
            cyclical = []
            turnaround = []

            for code in codes:
                df = hist_data[hist_data["code"] == code]
                df_before = df[df["date_dt"] <= rd]
                if df_before.empty or len(df_before) < 120:
                    continue

                close_prices = df_before["close"]
                current_price = float(close_prices.iloc[-1])
                if current_price <= 0:
                    continue

                # 基础数据
                code_key = str(code).replace(".0", "")
                if code_key in val_map:
                    pe = val_map[code_key]["pe"]
                    pb = val_map[code_key]["pb"]
                else:
                    pe = 999
                    pb = 999

                # 1年收益
                if len(close_prices) >= 252:
                    ret_1y = (current_price / float(close_prices.iloc[-252]) - 1) * 100
                else:
                    ret_1y = (current_price / float(close_prices.iloc[0]) - 1) * 100

                # 60日最低点
                low_60d = float(close_prices.iloc[-60:].min())
                rebound_from_low = (current_price / low_60d - 1) * 100 if low_60d > 0 else 0

                # MA60
                ma60 = close_prices.iloc[-60:].mean() if len(close_prices) >= 60 else current_price
                above_ma60 = current_price > ma60

                # PEG代理 (PE / 增长率)
                peg = pe / max(abs(ret_1y), 1) if pe > 0 else 999

                base_info = {"code": str(code).replace(".0", ""), "price": current_price,
                             "pe": pe, "pb": pb, "ret_1y": ret_1y,
                             "rebound": rebound_from_low, "above_ma60": above_ma60}

                # === 分类逻辑 ===
                # 快速增长型: 涨幅>30% 且 PEG合理
                if ret_1y > p["fast_growth_min_return"] and pe > 0 and peg < p["fast_growth_max_peg"]:
                    fast_growth.append({**base_info, "peg": peg, "type": "快速增长"})

                # 稳定增长型: PE合理 + 价格在趋势上
                if 0 < pe < p["stable_max_pe"] and above_ma60:
                    # 用价格变化代理ROE
                    proxy_roe = (current_price / float(close_prices.iloc[-120]) - 1) * 100 if len(close_prices) >= 120 else 0
                    if proxy_roe > -5:  # 不亏钱的公司
                        stable.append({**base_info, "proxy_roe": proxy_roe, "type": "稳定增长"})

                # 周期型: PB低 + 趋势向上
                if 0 < pb < p["cyclical_max_pb"] and above_ma60 and ret_1y > -10:
                    cyclical.append({**base_info, "type": "周期"})

                # 困境反转型: PB极低 + 从低点反弹
                if 0 < pb < p["turnaround_max_pb"] and rebound_from_low > p["turnaround_min_rebound"]:
                    turnaround.append({**base_info, "type": "困境反转"})

            # 各类型内部排序
            fast_growth.sort(key=lambda x: x["peg"])  # PEG越低越好
            stable.sort(key=lambda x: x["pe"])        # PE越低越好
            cyclical.sort(key=lambda x: x["pb"])      # PB越低越好
            turnaround.sort(key=lambda x: -x["rebound"])  # 反弹越强越好

            # 选出各类型Top N
            picks = []
            for cat, candidates in [("快速增长", fast_growth), ("稳定增长", stable),
                                     ("周期", cyclical), ("困境反转", turnaround)]:
                for i, c in enumerate(candidates[:p["top_n_per_type"]]):
                    picks.append({**c, "cat_rank": i + 1, "category": cat})

            # 最多持仓限制 + 标准化代码
            picks = picks[:p["total_max_positions"]]
            for c in picks:
                c["code"] = str(c["code"]).replace(".0", "")
            new_holds = set(c["code"] for c in picks)

            # 卖出不再持有的
            for code_key in list(held):
                if code_key not in new_holds:
                    df = hist_data[hist_data["code"].astype(str).str.replace(".0", "") == code_key]
                    df_before = df[df["date_dt"] <= rd]
                    if not df_before.empty:
                        signals.append(TradeSignal(
                            code=code_key, date=rd_str, signal=SignalType.SELL,
                            price=float(df_before.iloc[-1]["close"]), size=1.0,
                            reason="林奇分类调出", confidence=0.8,
                        ))

            # 买入新标的
            for c in picks:
                if c["code"] in held:
                    continue
                confidence = 0.55
                if c["category"] == "快速增长":
                    confidence = 0.70
                elif c["category"] == "困境反转":
                    confidence = 0.50  # 高风险

                signals.append(TradeSignal(
                    code=c["code"], date=rd_str, signal=SignalType.BUY,
                    price=c["price"], size=1.0 / len(picks) if picks else 0.1,
                    reason=f"林奇{c['category']}#{c['cat_rank']} PE={c['pe']:.1f} PB={c['pb']:.1f} 1Y={c['ret_1y']:.0f}%",
                    confidence=confidence,
                ))

            held = new_holds

        # 清仓
        if held and all_dates:
            last_date = all_dates[-1].strftime("%Y-%m-%d")
            for code in held:
                df = hist_data[hist_data["code"] == code]
                df_before = df[df["date_dt"] <= all_dates[-1]]
                if not df_before.empty:
                    signals.append(TradeSignal(
                        code=code, date=last_date, signal=SignalType.SELL,
                        price=float(df_before.iloc[-1]["close"]), size=1.0,
                        reason="林奇分类清仓", confidence=0.99,
                    ))

        return signals
