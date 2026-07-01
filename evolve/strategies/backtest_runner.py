"""
Real Backtest Runner — 用真实数据跑策略回测。

不依赖 stock-analyzer 的完整环境，可独立运行。
对比多个策略在相同数据上的表现，产出排名。
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

# 路径设置
EVOLVE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOCK_ROOT = os.path.join(os.path.dirname(EVOLVE_ROOT), "project", "stock-analyzer")
sys.path.insert(0, STOCK_ROOT)
sys.path.insert(0, os.path.join(STOCK_ROOT, "stock_analyzer"))

CACHE_DIR = os.path.join(STOCK_ROOT, "data", "cache")
OUTPUT_DIR = os.path.join(EVOLVE_ROOT, "reports")


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """加载真实 K 线和估值数据。"""
    kline_path = os.path.join(CACHE_DIR, "a_kline_500d_v2.csv")
    val_path = os.path.join(CACHE_DIR, "a_valuation_v1.csv")

    kline = pd.read_csv(kline_path) if os.path.exists(kline_path) else pd.DataFrame()
    valuation = pd.read_csv(val_path) if os.path.exists(val_path) else pd.DataFrame()

    return kline, valuation


def run_strategy_backtest(strategy_obj, kline: pd.DataFrame,
                          valuation: pd.DataFrame | None = None,
                          initial_capital: float = 1_000_000,
                          commission: float = 0.0003) -> dict:
    """运行单个策略的回测。

    返回绩效指标字典。
    """
    try:
        # 生成信号
        signals = strategy_obj.generate_signals(kline, valuation=valuation)

        if not signals:
            return {
                "strategy": strategy_obj.name,
                "error": "无交易信号",
                "annual_return": 0, "sharpe_ratio": 0,
                "max_drawdown": 0, "win_rate": 0,
                "profit_factor": 0, "total_trades": 0,
                "total_return": 0,
            }
    except Exception as e:
        return {
            "strategy": strategy_obj.name,
            "error": str(e),
            "annual_return": 0, "sharpe_ratio": 0,
            "max_drawdown": 0, "win_rate": 0,
            "profit_factor": 0, "total_trades": 0,
            "total_return": 0,
        }

    # 信号 → 模拟成交
    trades, equity_curve = _simulate(signals, kline, initial_capital, commission)

    # 计算指标
    metrics = _compute_metrics(equity_curve, trades, initial_capital)
    metrics["strategy"] = strategy_obj.name
    return metrics


def _simulate(signals, kline, capital, commission):
    """简化的回测模拟引擎。"""
    # 构建价格查找表
    price_map = {}
    for _, row in kline.iterrows():
        price_map[(str(row["code"]), str(row["date"]))] = float(row["close"])

    # 按日期排序
    sorted_signals = sorted(signals, key=lambda s: (s.date, 0 if str(s.signal) == "SELL" else 1))

    trades = []
    positions = {}
    cash = float(capital)
    total_capital = float(capital)
    equity_curve = []

    # 获取所有交易日期
    all_dates = sorted(set(s.date for s in sorted_signals))

    for date in all_dates:
        day_signals = [s for s in sorted_signals if s.date == date]

        for sig in day_signals:
            price = sig.price if sig.price > 0 else price_map.get((sig.code, date), 0)
            if price <= 0:
                continue

            if str(sig.signal) == "BUY":
                # 计算仓位大小
                max_alloc = cash * sig.size * 0.95  # 留5%缓冲
                if max_alloc < 1000:  # 最小交易金额
                    continue
                shares = int(max_alloc / price / 100) * 100
                if shares == 0:
                    continue
                cost = shares * price * (1 + commission)
                if cost > cash:
                    continue
                cash -= cost
                positions[sig.code] = positions.get(sig.code, 0) + shares
                trades.append({
                    "date": date, "code": sig.code, "action": "BUY",
                    "price": price, "shares": shares, "cost": cost,
                    "confidence": sig.confidence,
                })

            elif str(sig.signal) == "SELL":
                if sig.code not in positions or positions[sig.code] <= 0:
                    continue
                shares = positions[sig.code]
                revenue = shares * price * (1 - commission)
                cash += revenue
                del positions[sig.code]
                trades.append({
                    "date": date, "code": sig.code, "action": "SELL",
                    "price": price, "shares": shares, "revenue": revenue,
                })

        # Mark-to-market
        position_value = 0
        for code, shares in positions.items():
            px = price_map.get((code, date), 0)
            if px <= 0 and trades:
                # 用最近已知价格
                for t in reversed(trades):
                    if t["code"] == code:
                        px = t["price"]
                        break
            position_value += shares * px

        equity = cash + position_value
        equity_curve.append({"date": date, "equity": equity})

    return trades, pd.DataFrame(equity_curve)


def _compute_metrics(equity, trades, initial_capital):
    """计算绩效指标。"""
    if equity.empty or len(equity) < 2:
        return {
            "annual_return": 0, "sharpe_ratio": 0, "max_drawdown": 0,
            "win_rate": 0, "profit_factor": 0, "total_trades": 0,
            "total_return": 0, "final_equity": initial_capital,
        }

    eq = equity["equity"].values
    total_return = (eq[-1] / initial_capital - 1) * 100
    # 年化收益: use actual calendar days between first and last equity point
    if "date" in equity.columns and len(equity) >= 2:
        from datetime import datetime
        d1 = datetime.strptime(str(equity["date"].iloc[0])[:10], "%Y-%m-%d")
        d2 = datetime.strptime(str(equity["date"].iloc[-1])[:10], "%Y-%m-%d")
        actual_days = max((d2 - d1).days, 1)
    else:
        actual_days = len(equity)
    annual_return = ((1 + total_return / 100) ** (365 / actual_days) - 1) * 100

    # 夏普
    daily_rets = np.diff(eq) / eq[:-1]
    sharpe = (daily_rets.mean() / daily_rets.std() * np.sqrt(252)) if daily_rets.std() > 0 else 0

    # 最大回撤
    peak = np.maximum.accumulate(eq)
    drawdowns = (eq - peak) / peak * 100
    max_dd = float(drawdowns.min())

    # 胜率 & 盈亏比
    buy_trades = [t for t in trades if t["action"] == "BUY"]
    sell_trades = [t for t in trades if t["action"] == "SELL"]

    if buy_trades and sell_trades:
        profits = []
        # 按FIFO匹配买卖
        for bt in buy_trades:
            matching_sells = [s for s in sell_trades if s["code"] == bt["code"] and s["date"] >= bt["date"]]
            if matching_sells:
                st = matching_sells[0]
                pnl = (st["price"] - bt["price"]) / bt["price"] * 100
                profits.append(pnl)
                sell_trades.remove(st)

        if profits:
            win_rate = sum(1 for p in profits if p > 0) / len(profits) * 100
            total_profit = sum(p for p in profits if p > 0)
            total_loss = abs(sum(p for p in profits if p < 0))
            profit_factor = total_profit / total_loss if total_loss > 0 else 99
        else:
            win_rate, profit_factor = 0, 0
    else:
        win_rate, profit_factor = 0, 0

    return {
        "total_return": round(total_return, 2),
        "annual_return": round(annual_return, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown": round(max_dd, 2),
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "total_trades": len(trades),
        "buy_count": len([t for t in trades if t["action"] == "BUY"]),
        "sell_count": len([t for t in trades if t["action"] == "SELL"]),
        "final_equity": round(float(eq[-1]), 0),
    }


def run_all_strategies(strategies: list, kline=None, valuation=None) -> dict:
    """运行所有策略的回测对比。"""
    if kline is None:
        kline, valuation = load_data()

    if kline.empty:
        return {"error": "无K线数据", "timestamp": datetime.now().isoformat()}

    results = {}
    for strat_class in strategies:
        try:
            strat = strat_class()
            metrics = run_strategy_backtest(strat, kline, valuation)
            results[strat.name] = metrics
            print(f"  {strat.name:25s} 年化:{metrics.get('annual_return',0):6.1f}%  "
                  f"夏普:{metrics.get('sharpe_ratio',0):5.2f}  "
                  f"回撤:{metrics.get('max_drawdown',0):5.1f}%  "
                  f"胜率:{metrics.get('win_rate',0):4.1f}%")
        except Exception as e:
            print(f"  {strat_class.name:25s} ERROR: {e}")
            results[strat_class.name] = {"error": str(e)}

    # 排名
    ranked = sorted(
        [(k, v) for k, v in results.items() if "error" not in v],
        key=lambda x: x[1].get("sharpe_ratio", 0), reverse=True,
    )

    summary = {
        "timestamp": datetime.now().isoformat(),
        "strategies_tested": len(strategies),
        "rankings": [{"rank": i+1, "strategy": k, **v} for i, (k, v) in enumerate(ranked)],
    }

    # 保存结果
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    outpath = os.path.join(OUTPUT_DIR, f"backtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return summary


def main():
    """入口：加载所有策略，运行回测，打印排名。"""
    print("=" * 70)
    print("  Strategy Backtest Comparison")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    kline, valuation = load_data()
    print(f"\n数据: {len(kline)} 条K线, {kline['code'].nunique()} 只股票")
    print(f"日期: {kline['date'].min()} ~ {kline['date'].max()}")
    print()

    # 加载策略
    strategies = []
    for mod_name in ["graham_defensive", "magic_formula", "dual_momentum", "can_slim"]:
        try:
            mod = __import__(f"strategies.{mod_name}", fromlist=["*"])
            for attr in dir(mod):
                obj = getattr(mod, attr)
                if isinstance(obj, type) and hasattr(obj, 'name') and obj.name == mod_name:
                    strategies.append(obj)
                    break
        except Exception as e:
            print(f"  加载 {mod_name} 失败: {e}")

    if not strategies:
        # 直接导入
        from strategies.graham_defensive import GrahamDefensiveStrategy
        from strategies.magic_formula import MagicFormulaStrategy
        from strategies.dual_momentum import DualMomentumStrategy
        from strategies.can_slim import CanSlimStrategy
        strategies = [GrahamDefensiveStrategy, MagicFormulaStrategy,
                      DualMomentumStrategy, CanSlimStrategy]

    print(f"策略数: {len(strategies)}\n")
    results = run_all_strategies(strategies, kline, valuation)

    # 打印排名
    print(f"\n{'='*70}")
    print("  Final Rankings (by Sharpe)")
    print(f"{'='*70}")
    for r in results.get("rankings", []):
        print(f"  #{r['rank']} {r['strategy']:25s}  "
              f"年化:{r.get('annual_return',0):6.1f}%  "
              f"夏普:{r.get('sharpe_ratio',0):5.2f}  "
              f"最大回撤:{r.get('max_drawdown',0):5.1f}%  "
              f"胜率:{r.get('win_rate',0):4.1f}%  "
              f"盈亏比:{r.get('profit_factor',0):4.2f}")

    print(f"\n结果已保存到: {OUTPUT_DIR}")
    return results


if __name__ == "__main__":
    main()
