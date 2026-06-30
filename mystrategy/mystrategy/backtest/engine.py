"""Event-driven backtesting engine.

Supports A-stock constraints: T+1, price limits, lot rounding,
commission + stamp tax.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import numpy as np

from mystrategy.backtest.broker import SimulatedBroker, BrokerConfig


@dataclass
class BacktestResult:
    """Complete backtest results."""
    initial_capital: float = 0
    final_value: float = 0
    total_return: float = 0
    annual_return: float = 0
    max_drawdown: float = 0
    sharpe_ratio: float = 0
    calmar_ratio: float = 0
    win_rate: float = 0
    total_trades: int = 0
    daily_returns: list[float] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    trade_log: list[dict] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


def run_backtest(
    strategy_cls,
    data: dict[str, pd.DataFrame],
    config: BrokerConfig | None = None,
    strategy_params: dict | None = None,
    benchmark_kline: pd.DataFrame | None = None,
) -> BacktestResult:
    """Run a backtest with the event-driven engine.

    Args:
        strategy_cls: Strategy class (not instance)
        data: dict with 'kline' DataFrame (must have date, open, high, low, close, volume)
        config: Broker configuration
        strategy_params: Strategy-specific parameters
        benchmark_kline: Benchmark (e.g., CSI 300) for alpha calculation

    Returns:
        BacktestResult with full performance metrics
    """
    broker_cfg = config or BrokerConfig()
    broker = SimulatedBroker(broker_cfg)
    broker.set_data(data["kline"])

    strategy = strategy_cls(params=strategy_params)

    equity_curve = [broker_cfg.initial_capital]
    dates = []

    # Walk through each trading day
    for day in range(len(broker._data)):
        broker._date_idx = day

        # Get historical data up to current day
        hist_data = {
            "kline": broker._data.iloc[:day + 1].copy(),
            "weekly_kline": data.get("weekly_kline"),
        }

        # Generate signals
        strategy.init(hist_data)
        if strategy.pre_check():
            signals = strategy.generate_signals()

            for sig in signals:
                if sig.signal_type.value == "BUY":
                    broker.buy(code=broker._data["code"].iloc[0] if "code" in broker._data.columns else data.get("code", "?"),
                              price=sig.price, amount=broker.account.cash * 0.1)
                elif sig.signal_type.value == "SELL":
                    broker.sell(code=broker._data["code"].iloc[0] if "code" in broker._data.columns else data.get("code", "?"),
                               price=sig.price, pct=1.0)

        # Record equity
        state = broker.get_portfolio_state()
        equity_curve.append(state["total_value"])
        dates.append(broker.current_date)

    # Calculate performance metrics
    return _calculate_metrics(broker, equity_curve, dates, benchmark_kline, broker_cfg)


def _calculate_metrics(
    broker: SimulatedBroker,
    equity_curve: list[float],
    dates: list[str],
    benchmark: pd.DataFrame | None,
    config: BrokerConfig,
) -> BacktestResult:
    """Calculate comprehensive performance metrics."""

    initial = config.initial_capital
    final = equity_curve[-1] if equity_curve else initial
    total_return = (final / initial - 1) * 100

    # Daily returns
    daily_r = []
    for i in range(1, len(equity_curve)):
        if equity_curve[i - 1] > 0:
            daily_r.append(equity_curve[i] / equity_curve[i - 1] - 1)

    # Annual return (252 trading days)
    if len(daily_r) > 0:
        annual_return = ((1 + total_return / 100) ** (252 / len(daily_r)) - 1) * 100
    else:
        annual_return = 0

    # Max drawdown
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = (peak - val) / peak
        if dd > max_dd:
            max_dd = dd
    max_dd *= 100

    # Sharpe ratio
    if daily_r and np.std(daily_r) > 0:
        sharpe = np.mean(daily_r) / np.std(daily_r) * np.sqrt(252)
    else:
        sharpe = 0

    # Calmar ratio
    calmar = annual_return / max_dd if max_dd > 0 else 0

    # Win rate
    trades = broker.account.trade_log
    buy_trades = [t for t in trades if t["action"] == "SELL"]
    if buy_trades:
        wins = 0
        for i in range(0, len(buy_trades)):
            # Match sell with preceding buy
            sell = buy_trades[i]
            # Find matching buy
            prev_buys = [t for t in trades[:trades.index(sell)] if t["action"] == "BUY" and t["code"] == sell["code"]]
            if prev_buys and sell.get("proceeds", 0) > prev_buys[-1].get("cost", 0):
                wins += 1
        win_rate = wins / len(buy_trades) * 100 if buy_trades else 0
    else:
        win_rate = 0

    # Benchmark comparison
    alpha = 0.0
    if benchmark is not None and not benchmark.empty:
        bench_ret = (benchmark["close"].iloc[-1] / benchmark["close"].iloc[0] - 1) * 100
        alpha = total_return - bench_ret
    else:
        bench_ret = 0.0

    return BacktestResult(
        initial_capital=initial,
        final_value=final,
        total_return=total_return,
        annual_return=annual_return,
        max_drawdown=max_dd,
        sharpe_ratio=sharpe,
        calmar_ratio=calmar,
        win_rate=win_rate,
        total_trades=len(trades),
        daily_returns=daily_r,
        equity_curve=equity_curve,
        trade_log=trades,
        metrics={
            "benchmark_return": bench_ret if benchmark is not None else None,
            "alpha": alpha,
            "total_buys": len([t for t in trades if t["action"] == "BUY"]),
            "total_sells": len([t for t in trades if t["action"] == "SELL"]),
        },
    )
