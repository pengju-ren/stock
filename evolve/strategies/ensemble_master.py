"""
Ensemble Master — 融合4个子策略信号,按共识度选出最强标的
"""

from __future__ import annotations
import numpy as np, pandas as pd

from strategies.base import BaseStrategy, SignalType, TradeSignal
try:
    from stock_analyzer.strategies.base import register_strategy
except ImportError:
    def register_strategy(cls): return cls


@register_strategy
class EnsembleMasterStrategy(BaseStrategy):
    """多策略信号融合,共识度越高买入优先级越高。"""

    name = "ensemble_master"

    @staticmethod
    def default_params() -> dict:
        return {"top_n": 8, "rebalance_days": 21, "drop_n": 1}

    def generate_signals(self, hist_data, stock_list=None, valuation=None, **kwargs):
        p = self.params
        signals = []

        if hist_data is None or hist_data.empty:
            return signals

        hist_data = hist_data.copy()
        hist_data["date_dt"] = pd.to_datetime(hist_data["date"])
        all_dates = sorted(hist_data["date_dt"].unique())
        if len(all_dates) < 120:
            return signals

        # Import and run sub-strategies once
        from strategies.can_slim import CanSlimStrategy
        from strategies.dual_momentum import DualMomentumStrategy
        from strategies.alpha_composite import AlphaCompositeStrategy
        from strategies.etf_rotation import ETFSectorRotationStrategy

        sub_strategies = [
            (CanSlimStrategy(), "can_slim"),
            (DualMomentumStrategy(), "dual_momentum"),
            (AlphaCompositeStrategy(), "alpha_composite"),
            (ETFSectorRotationStrategy(), "etf_rotation"),
        ]

        # Pre-generate all signals, indexed by date
        sub_buys = {}
        for strat_obj, name in sub_strategies:
            try:
                all_sig = strat_obj.generate_signals(hist_data, stock_list=stock_list, valuation=valuation)
                by_date = {}
                for s in all_sig:
                    if str(s.signal) == "BUY":
                        d = str(s.date)[:10]
                        by_date.setdefault(d, []).append(s)
                sub_buys[name] = by_date
            except Exception:
                sub_buys[name] = {}

        rebalance_dates = [all_dates[i] for i in range(120, len(all_dates), p["rebalance_days"])]
        held = set()

        for rd in rebalance_dates:
            rd_str = rd.strftime("%Y-%m-%d")

            # Collect all buy signals for this date across all strategies
            merged_signals = {}
            for name, buys_by_date in sub_buys.items():
                for s in buys_by_date.get(rd_str, []):
                    ck = str(s.code).replace(".0", "")
                    if ck not in merged_signals:
                        merged_signals[ck] = {"code": ck, "price": s.price, "strategies": set(), "best_conf": 0}
                    merged_signals[ck]["strategies"].add(name)
                    merged_signals[ck]["best_conf"] = max(merged_signals[ck]["best_conf"], s.confidence)

            # Score: consensus count * 3 (more strategies = higher conviction)
            ranked = []
            for ck, info in merged_signals.items():
                info["n_strat"] = len(info["strategies"])
                info["score"] = info["n_strat"] * 3
                ranked.append(info)

            ranked.sort(key=lambda x: x["score"], reverse=True)

            # TopKDropout
            if p["drop_n"] > 0 and len(ranked) > p["top_n"] + p["drop_n"]:
                ranked.pop(np.random.randint(p["top_n"], len(ranked)))

            to_buy = ranked[:p["top_n"]]
            new_holds = set(c["code"] for c in to_buy)

            # Sell old
            for ck in list(held):
                if ck not in new_holds:
                    df = hist_data[hist_data["code"].astype(str).str.replace(".0","") == ck]
                    dfb = df[df["date_dt"] <= rd]
                    if not dfb.empty:
                        signals.append(TradeSignal(code=ck, date=rd_str, signal=SignalType.SELL,
                            price=float(dfb.iloc[-1]["close"]), size=1.0,
                            reason="Ensemble调出", confidence=0.85))

            # Buy new
            n = len(to_buy)
            for c in to_buy:
                if c["code"] in held:
                    continue
                names = "+".join(sorted(c["strategies"]))
                signals.append(TradeSignal(code=c["code"], date=rd_str, signal=SignalType.BUY,
                    price=c["price"], size=1.0 / max(n, 1),
                    reason=f"Ensemble {c['n_strat']}/4: {names}",
                    confidence=min(0.90, 0.45 + c["n_strat"] * 0.12)))

            held = new_holds

        # Final liquidation
        if held and all_dates:
            ld = all_dates[-1].strftime("%Y-%m-%d")
            for ck in held:
                df = hist_data[hist_data["code"].astype(str).str.replace(".0","") == ck]
                dfb = df[df["date_dt"] <= all_dates[-1]]
                if not dfb.empty:
                    signals.append(TradeSignal(code=ck, date=ld, signal=SignalType.SELL,
                        price=float(dfb.iloc[-1]["close"]), size=1.0,
                        reason="Ensemble清仓", confidence=0.99))

        return signals
