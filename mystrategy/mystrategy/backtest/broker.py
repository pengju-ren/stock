"""Simulated broker for A-stock trading.

Models: T+1 settlement, price limits (±10%/±20%), lot rounding (100 shares),
commission (0.03%), stamp tax (sell only 0.1%).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class BrokerConfig:
    initial_capital: float = 1_000_000
    commission_rate: float = 0.0003   # A-stock: 0.03%
    stamp_tax_rate: float = 0.001     # Sell only: 0.1%
    min_lot: int = 100                # 100 shares/lot
    slippage: float = 0.001           # 0.1% slippage
    t_plus_1: bool = True             # T+1 settlement
    price_limit_pct: float = 0.10     # Main board: ±10%


@dataclass
class Account:
    cash: float
    positions: dict[str, dict[str, Any]] = field(default_factory=dict)
    trade_log: list[dict] = field(default_factory=list)

    @property
    def total_value(self) -> float:
        return self.cash + sum(
            p.get("market_value", 0) for p in self.positions.values()
        )

    @property
    def pnl(self) -> float:
        return self.total_value - self.initial_capital

    def __post_init__(self):
        self.initial_capital = self.cash


class SimulatedBroker:
    """Simulated broker with A-stock trading constraints."""

    def __init__(self, config: BrokerConfig | None = None):
        self.config = config or BrokerConfig()
        self.account = Account(cash=self.config.initial_capital)
        self._data: pd.DataFrame | None = None
        self._date_idx: int = 0
        self._pending_buys: dict[str, int] = {}  # T+1: buys settle next day

    def set_data(self, df: pd.DataFrame):
        """Set the price data for simulation."""
        self._data = df.sort_values("date").reset_index(drop=True)
        self._date_idx = 0

    @property
    def current_date(self):
        if self._data is None:
            return None
        return self._data["date"].iloc[self._date_idx]

    @property
    def current_price(self, code: str = "") -> float:
        if self._data is None:
            return 0.0
        return float(self._data["close"].iloc[self._date_idx])

    def advance_day(self):
        """Move to next trading day. Process T+1 settlements."""
        if self._data is None or self._date_idx >= len(self._data) - 1:
            return False
        self._date_idx += 1

        # Process T+1: settled buys become available
        for code, shares in list(self._pending_buys.items()):
            if code in self.account.positions:
                self.account.positions[code]["available"] += shares
            del self._pending_buys[code]

        # Update market values
        for code, pos in self.account.positions.items():
            pos["market_value"] = pos["shares"] * self.current_price

        return True

    def buy(self, code: str, price: float, shares: int | None = None,
            amount: float | None = None) -> dict | None:
        """Execute a buy order.

        Args:
            code: stock code
            price: execution price (after slippage)
            shares: exact number of shares (rounded to lot)
            amount: cash amount to spend (will calc shares automatically)

        Returns:
            Trade dict or None if rejected.
        """
        # Check price limits
        if self._data is not None:
            prev_close = self._data["close"].iloc[max(0, self._date_idx - 1)]
            limit_up = prev_close * (1 + self.config.price_limit_pct)
            if price > limit_up:
                return None  # Can't buy at limit-up price

        # Calculate shares
        if shares is None and amount is not None:
            shares = int(amount / price / self.config.min_lot) * self.config.min_lot
        elif shares is not None:
            shares = shares // self.config.min_lot * self.config.min_lot

        if not shares or shares <= 0:
            return None

        # Apply slippage
        exec_price = price * (1 + self.config.slippage)
        cost = exec_price * shares + exec_price * shares * self.config.commission_rate

        if cost > self.account.cash:
            # Scale down to available cash
            max_shares = int(
                self.account.cash / (exec_price * (1 + self.config.commission_rate))
                / self.config.min_lot
            ) * self.config.min_lot
            if max_shares < self.config.min_lot:
                return None
            shares = max_shares
            cost = exec_price * shares * (1 + self.config.commission_rate)

        # Execute
        self.account.cash -= cost

        if code not in self.account.positions:
            self.account.positions[code] = {"shares": 0, "available": 0, "avg_cost": 0, "market_value": 0}

        pos = self.account.positions[code]
        avg_cost = (
            (pos["avg_cost"] * pos["shares"] + exec_price * shares) / (pos["shares"] + shares)
            if pos["shares"] else exec_price
        )
        pos["shares"] += shares
        pos["avg_cost"] = avg_cost
        pos["market_value"] = pos["shares"] * self.current_price

        if self.config.t_plus_1:
            self._pending_buys[code] = self._pending_buys.get(code, 0) + shares
        else:
            pos["available"] += shares

        trade = {
            "date": self.current_date, "action": "BUY", "code": code,
            "price": exec_price, "shares": shares, "cost": cost, "commission": cost - exec_price * shares,
        }
        self.account.trade_log.append(trade)
        return trade

    def sell(self, code: str, price: float, shares: int | None = None,
             pct: float | None = None) -> dict | None:
        """Execute a sell order."""
        if code not in self.account.positions:
            return None

        pos = self.account.positions[code]
        available = pos.get("available", pos["shares"])

        if shares is None and pct is not None:
            shares = int(pos["shares"] * pct / self.config.min_lot) * self.config.min_lot
        elif shares is not None:
            shares = min(shares, available)
            shares = shares // self.config.min_lot * self.config.min_lot

        if not shares or shares <= 0:
            return None

        # Check price limits
        if self._data is not None:
            prev_close = self._data["close"].iloc[max(0, self._date_idx - 1)]
            limit_down = prev_close * (1 - self.config.price_limit_pct)
            if price < limit_down:
                return None  # Can't sell at limit-down

        exec_price = price * (1 - self.config.slippage)
        proceeds = exec_price * shares
        commission = proceeds * self.config.commission_rate
        stamp_tax = proceeds * self.config.stamp_tax_rate

        self.account.cash += proceeds - commission - stamp_tax
        pos["shares"] -= shares
        pos["available"] = pos.get("available", 0) - min(shares, pos.get("available", 0))
        pos["market_value"] = pos["shares"] * self.current_price

        if pos["shares"] <= 0:
            del self.account.positions[code]

        trade = {
            "date": self.current_date, "action": "SELL", "code": code,
            "price": exec_price, "shares": shares, "proceeds": proceeds,
            "commission": commission, "stamp_tax": stamp_tax,
        }
        self.account.trade_log.append(trade)
        return trade

    def get_portfolio_state(self) -> dict:
        """Get current portfolio summary."""
        positions_value = sum(
            p["shares"] * self.current_price for p in self.account.positions.values()
        )
        return {
            "date": self.current_date,
            "cash": self.account.cash,
            "positions_value": positions_value,
            "total_value": self.account.cash + positions_value,
            "pnl": self.account.cash + positions_value - self.account.initial_capital,
            "positions": self.account.positions.copy(),
        }
