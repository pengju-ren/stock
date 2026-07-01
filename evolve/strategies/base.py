"""
Strategy Base Class for evolve strategies.

Works with or without stock-analyzer installed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class SignalType:
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class TradeSignal:
    def __init__(self, code, date, signal, price=0, size=1, reason="", confidence=0.5, metadata=None):
        self.code = code
        self.date = date
        self.signal = signal
        self.price = price
        self.size = size
        self.reason = reason
        self.confidence = confidence
        self.metadata = metadata or {}


class BaseStrategy:
    name = "base"
    params: dict = {}

    def __init__(self, **kwargs):
        self.params = {**self.default_params(), **kwargs}

    @staticmethod
    def default_params() -> dict:
        return {}

    def generate_signals(self, hist_data, stock_list=None, **kwargs):
        raise NotImplementedError


# Try to use stock-analyzer's versions if available
try:
    from stock_analyzer.strategies.base import (
        BaseStrategy as SABaseStrategy,
        SignalType as SASignalType,
        TradeSignal as SATradeSignal,
    )
    # Use stock-analyzer versions (more complete)
    BaseStrategy = SABaseStrategy
    SignalType = SASignalType
    TradeSignal = SATradeSignal
    USING_SA = True
except ImportError:
    USING_SA = False
