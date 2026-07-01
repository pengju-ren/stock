"""
ETF Sector Rotation Strategy — 行业轮动策略

来源: stock-analyzer已验证最优策略 (+136.64%, 夏普1.09)
      招商证券行业动量改进 + 国金证券ETF轮动模型

核心逻辑:
  1. 将申万行业映射到8大板块
  2. 每期计算各板块的综合动量得分
  3. 在每个板块内选动量最强的N只股票作为板块代理
  4. 月度再平衡

8大板块映射:
  消费/科技/金融/医药/新能源/军工/周期/红利

已验证的最佳参数(来自stock-analyzer迭代):
  top_k=5, picks_per_sector=3, monthly rebalance
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.base import BaseStrategy, SignalType, TradeSignal
try:
    from stock_analyzer.strategies.base import register_strategy
except ImportError:
    def register_strategy(cls): return cls


# 行业→板块映射
INDUSTRY_TO_SECTOR = {
    "酒、饮料和精制茶制造业": "消费", "食品制造业": "消费", "批发业": "消费",
    "零售业": "消费", "纺织服装、服饰业": "消费", "家具制造业": "消费",
    "计算机、通信和其他电子设备制造业": "科技", "软件和信息技术服务业": "科技",
    "互联网和相关服务": "科技", "电信、广播电视和卫星传输服务": "科技",
    "仪器仪表制造业": "科技",
    "货币金融服务": "金融", "资本市场服务": "金融", "其他金融业": "金融",
    "保险业": "金融", "房地产业": "金融",
    "医药制造业": "医药",
    "电气机械和器材制造业": "新能源", "汽车制造业": "新能源",
    "专用设备制造业": "新能源", "通用设备制造业": "新能源",
    "铁路、船舶、航空航天和其他运输设备制造业": "新能源",
    "黑色金属冶炼和压延加工业": "周期", "有色金属冶炼和压延加工业": "周期",
    "化学原料和化学制品制造业": "周期", "非金属矿物制品业": "周期",
    "石油和天然气开采业": "周期", "煤炭开采和洗选业": "周期",
    "电力、热力生产和供应业": "红利", "水的生产和供应业": "红利",
    "道路运输业": "红利", "航空运输业": "红利", "水上运输业": "红利",
    "公共设施管理业": "红利", "土木工程建筑业": "周期",
    "商务服务业": "消费", "批发业": "消费",
}


@register_strategy
class ETFSectorRotationStrategy(BaseStrategy):
    """ETF行业轮动 — 板块动量排名 + 板块内选龙头。

    参数(来自stock-analyzer最佳实践):
        top_k: 持仓板块数 (默认 4)
        picks_per_sector: 每板块选股数 (默认 2)
        momentum_weights: 短中长期权重 [1m, 3m, 6m]
        rebalance_days: 调仓周期 (默认 21)
    """

    name = "etf_rotation"

    @staticmethod
    def default_params() -> dict:
        return {
            "top_k": 4,
            "picks_per_sector": 2,
            "momentum_weights": [0.3, 0.3, 0.4],  # 1m, 3m, 6m
            "rebalance_days": 21,
            "max_positions": 10,
            "min_stocks_per_sector": 1,
        }

    def generate_signals(self, hist_data, stock_list=None, industries=None, **kwargs):
        p = self.params
        signals = []

        if hist_data is None or hist_data.empty:
            return signals

        hist_data = hist_data.copy()
        hist_data["date_dt"] = pd.to_datetime(hist_data["date"])
        all_dates = sorted(hist_data["date_dt"].unique())

        if len(all_dates) < 120:
            return signals

        # Build code→industry mapping
        code_to_industry = {}
        if industries is not None and not industries.empty:
            for _, row in industries.iterrows():
                code_to_industry[str(row["code"]).replace(".0", "")] = row.get("industry", "未知")

        # Build code→sector mapping
        code_to_sector = {}
        codes = sorted(hist_data["code"].unique())
        for code in codes:
            code_str = str(code).replace(".0", "")
            ind = code_to_industry.get(code_str, "未知")
            sector = INDUSTRY_TO_SECTOR.get(ind, "其他")
            code_to_sector[code_str] = sector

        rebalance_dates = [all_dates[i] for i in range(120, len(all_dates), p["rebalance_days"])]
        held = set()

        for rd in rebalance_dates:
            rd_str = rd.strftime("%Y-%m-%d")

            # Calculate momentum for each stock
            stock_momentum = {}
            for code in codes:
                code_str = str(code).replace(".0", "")
                df = hist_data[hist_data["code"] == code]
                df_before = df[df["date_dt"] <= rd]
                if df_before.empty or len(df_before) < 120:
                    continue

                close = df_before["close"]
                current = float(close.iloc[-1])
                if current <= 0:
                    continue

                # Multi-period momentum
                periods = [21, 63, 126]  # 1m, 3m, 6m
                mom_scores = []
                for period in periods:
                    if len(close) > period:
                        past = float(close.iloc[-period-1]) if len(close) > period + 1 else float(close.iloc[0])
                        mom_scores.append((current / past - 1) * 100)
                    else:
                        mom_scores.append(0)

                # Weighted momentum
                weighted_mom = sum(m * w for m, w in zip(mom_scores, p["momentum_weights"]))
                stock_momentum[code_str] = {
                    "code": code_str,
                    "price": current,
                    "momentum": weighted_mom,
                    "mom_1m": mom_scores[0] if len(mom_scores) > 0 else 0,
                    "mom_3m": mom_scores[1] if len(mom_scores) > 1 else 0,
                    "mom_6m": mom_scores[2] if len(mom_scores) > 2 else 0,
                    "sector": code_to_sector.get(code_str, "其他"),
                }

            # Aggregate to sector level
            sector_momentum = {}
            for info in stock_momentum.values():
                sec = info["sector"]
                if sec not in sector_momentum:
                    sector_momentum[sec] = []
                sector_momentum[sec].append(info["momentum"])

            sector_avg = {}
            for sec, moms in sector_momentum.items():
                if len(moms) >= p["min_stocks_per_sector"]:
                    sector_avg[sec] = sum(moms) / len(moms)

            # Rank sectors by momentum
            ranked_sectors = sorted(sector_avg.items(), key=lambda x: -x[1])

            # Pick top sectors and their best stocks
            picks = []
            for sec, _ in ranked_sectors[:p["top_k"]]:
                sec_stocks = [s for s in stock_momentum.values() if s["sector"] == sec]
                sec_stocks.sort(key=lambda x: -x["momentum"])
                for s in sec_stocks[:p["picks_per_sector"]]:
                    picks.append(s)

            picks = picks[:p["max_positions"]]
            new_holds = set(c["code"] for c in picks)

            # Sell
            for code_key in list(held):
                if code_key not in new_holds:
                    df = hist_data[hist_data["code"].astype(str).str.replace(".0", "") == code_key]
                    df_before = df[df["date_dt"] <= rd]
                    if not df_before.empty:
                        signals.append(TradeSignal(
                            code=code_key, date=rd_str, signal=SignalType.SELL,
                            price=float(df_before.iloc[-1]["close"]), size=1.0,
                            reason="行业轮动调出", confidence=0.8,
                        ))

            # Buy
            n_picks = len(picks)
            for c in picks:
                if c["code"] in held:
                    continue
                signals.append(TradeSignal(
                    code=c["code"], date=rd_str, signal=SignalType.BUY,
                    price=c["price"], size=1.0 / max(n_picks, 1),
                    reason=f'ETF轮动 {c["sector"]} M={c["momentum"]:.1f}% (1m:{c["mom_1m"]:.0f}% 3m:{c["mom_3m"]:.0f}% 6m:{c["mom_6m"]:.0f}%)',
                    confidence=min(0.85, 0.5 + abs(c["momentum"]) / 100),
                ))

            held = new_holds

        # Liquidation
        if held and all_dates:
            last_date = all_dates[-1].strftime("%Y-%m-%d")
            for code_key in held:
                df = hist_data[hist_data["code"].astype(str).str.replace(".0", "") == code_key]
                df_before = df[df["date_dt"] <= all_dates[-1]]
                if not df_before.empty:
                    signals.append(TradeSignal(
                        code=code_key, date=last_date, signal=SignalType.SELL,
                        price=float(df_before.iloc[-1]["close"]), size=1.0,
                        reason="行业轮动清仓", confidence=0.99,
                    ))

        return signals
