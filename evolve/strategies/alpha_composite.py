"""
Alpha Composite Strategy v3 — CAN SLIM + Dual Momentum + Trend 投票融合

三策略独立打分,至少2/3通过才买入,互相制衡降低过拟合。
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
class AlphaCompositeStrategy(BaseStrategy):
    """多策略投票融合。"""

    name = "alpha_composite"

    @staticmethod
    def default_params() -> dict:
        return {
            "top_n": 5, "rebalance_days": 21, "min_votes": 2,
            "cs_min_score": 3, "dm_lookback_months": 6, "dm_top_n": 5,
            "trend_ma_short": 20, "trend_ma_long": 60,
            "trailing_stop_atr": 2.5, "take_profit_pct": 50, "drop_n": 2,
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
        held = set()

        for rd in rebalance_dates:
            rd_str = rd.strftime("%Y-%m-%d")
            composite_scores = []

            for code in codes:
                df = hist_data[hist_data["code"] == code]
                df_before = df[df["date_dt"] <= rd]
                if df_before.empty or len(df_before) < 60:
                    continue

                close_prices = df_before["close"]
                volumes = df_before["volume"] if "volume" in df_before.columns else None
                current_price = float(close_prices.iloc[-1])
                votes, details = 0, []

                # Signal 1: CAN SLIM
                cs_score = 0
                if len(close_prices) >= 63:
                    if (current_price / float(close_prices.iloc[-63]) - 1) * 100 > 10:
                        cs_score += 1
                if len(close_prices) >= 252:
                    if (current_price / float(close_prices.iloc[-252]) - 1) * 100 > 15:
                        cs_score += 1
                if len(close_prices) >= 20:
                    if current_price >= close_prices.iloc[-20:].max() * 0.97:
                        cs_score += 1
                if volumes is not None and len(volumes) >= 20:
                    if volumes.iloc[-5:].mean() > volumes.iloc[-20:].mean() * 1.2:
                        cs_score += 1
                if cs_score >= p["cs_min_score"]:
                    votes += 1; details.append(f"CS:{cs_score}")

                # Signal 2: Dual Momentum
                lb = p["dm_lookback_months"] * 21
                if len(df_before) >= lb:
                    mom = (current_price / float(df_before.iloc[-lb]["close"]) - 1) * 100
                elif len(df_before) >= 60:
                    mom = (current_price / float(df_before.iloc[-60]["close"]) - 1) * 100
                else:
                    mom = 0
                if mom > 0:
                    votes += 1; details.append(f"DM:{mom:.0f}%")

                # Signal 3: Trend (Weinstein Stage 2)
                if len(close_prices) >= p["trend_ma_long"]:
                    ma20 = close_prices.iloc[-p["trend_ma_short"]:].mean()
                    ma60 = close_prices.iloc[-p["trend_ma_long"]:].mean()
                    if current_price > ma20 > ma60:
                        votes += 1; details.append("Stage2")
                    elif current_price > ma60:
                        votes += 0.5; details.append(">MA60")

                if votes >= p["min_votes"]:
                    composite_scores.append({
                        "code": code, "votes": votes,
                        "details": " + ".join(details), "price": current_price,
                        "score": votes * 10 + cs_score * 2 + abs(mom) * 0.1,
                    })

            composite_scores.sort(key=lambda x: x["score"], reverse=True)
            new_holds = set(c["code"] for c in composite_scores[:p["top_n"]])

            for code_key in list(held):
                if code_key not in new_holds:
                    df = hist_data[hist_data["code"].astype(str).str.replace(".0","") == code_key]
                    df_before = df[df["date_dt"] <= rd]
                    if not df_before.empty:
                        signals.append(TradeSignal(
                            code=code_key, date=rd_str, signal=SignalType.SELL,
                            price=float(df_before.iloc[-1]["close"]), size=1.0,
                            reason="调出", confidence=0.8))

            for c in composite_scores[:p["top_n"]]:
                if c["code"] in held:
                    continue
                signals.append(TradeSignal(
                    code=c["code"], date=rd_str, signal=SignalType.BUY,
                    price=c["price"], size=1.0 / p["top_n"],
                    reason=f"Alpha {c['votes']}/3: {c['details']}",
                    confidence=min(0.9, 0.4 + c["votes"] * 0.15)))

            held = new_holds

        if held and all_dates:
            ld = all_dates[-1].strftime("%Y-%m-%d")
            for code_key in held:
                df = hist_data[hist_data["code"].astype(str).str.replace(".0","") == code_key]
                df_before = df[df["date_dt"] <= all_dates[-1]]
                if not df_before.empty:
                    signals.append(TradeSignal(
                        code=code_key, date=ld, signal=SignalType.SELL,
                        price=float(df_before.iloc[-1]["close"]), size=1.0,
                        reason="清仓", confidence=0.99))

        return signals
