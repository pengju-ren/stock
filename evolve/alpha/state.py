"""
进化引擎状态管理 — 持久化循环状态、预测账本、改进历史。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any

from .config import STATE_FILE, LEDGER_FILE


# ============================================================
# 进化循环状态
# ============================================================

@dataclass
class EvolutionState:
    """进化引擎的完整状态，跨 session 持久化。"""

    # 元信息
    version: str = "1.0.0"
    created_at: str = ""
    updated_at: str = ""

    # 循环计数
    total_cycles: int = 0
    successful_improvements: int = 0
    failed_attempts: int = 0

    # 当前循环
    current_cycle: int = 0
    cycle_started_at: str = ""
    cycle_phase: str = "idle"  # find | build | verify | ship | idle

    # 找到的弱点
    weaknesses_found: list[dict] = field(default_factory=list)
    # [{id, type, severity, description, found_at, status: open/fixing/fixed/wont_fix}]

    # 当前正在进行的改进
    active_improvement: dict | None = None
    # {weakness_id, goal, approach, attempt_count, started_at}

    # 已验证通过的改进（待合入）
    verified_improvements: list[dict] = field(default_factory=list)

    # 已合入的改进历史
    improvement_history: list[dict] = field(default_factory=list)
    # [{id, date, weakness, solution, verification_results, changelog_path}]

    # 归档的失败尝试
    failed_experiments: list[dict] = field(default_factory=list)

    # 因子健康状态快照
    factor_health_snapshot: dict = field(default_factory=dict)

    # 策略健康状态快照
    strategy_health_snapshot: dict = field(default_factory=dict)

    # 市场状态
    market_regime: str = "UNKNOWN"
    market_regime_changed_at: str = ""

    # 知识库状态
    knowledge_books_imported: int = 0
    knowledge_last_updated: str = ""

    # 上次扫描时间
    last_inspiration_scan: str = ""
    last_audit_run: str = ""
    last_factor_check: str = ""


def load_state() -> EvolutionState:
    """从磁盘加载进化状态。"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return _dict_to_state(data)
        except (json.JSONDecodeError, KeyError):
            pass
    return EvolutionState(created_at=datetime.now().isoformat())


def save_state(state: EvolutionState) -> None:
    """保存进化状态到磁盘。"""
    state.updated_at = datetime.now().isoformat()
    if not state.created_at:
        state.created_at = state.updated_at
    data = _state_to_dict(state)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _state_to_dict(state: EvolutionState) -> dict:
    """将 EvolutionState 转为可序列化的 dict。"""
    return {
        "version": state.version,
        "created_at": state.created_at,
        "updated_at": state.updated_at,
        "total_cycles": state.total_cycles,
        "successful_improvements": state.successful_improvements,
        "failed_attempts": state.failed_attempts,
        "current_cycle": state.current_cycle,
        "cycle_started_at": state.cycle_started_at,
        "cycle_phase": state.cycle_phase,
        "weaknesses_found": state.weaknesses_found,
        "active_improvement": state.active_improvement,
        "verified_improvements": state.verified_improvements,
        "improvement_history": state.improvement_history,
        "failed_experiments": state.failed_experiments,
        "factor_health_snapshot": state.factor_health_snapshot,
        "strategy_health_snapshot": state.strategy_health_snapshot,
        "market_regime": state.market_regime,
        "market_regime_changed_at": state.market_regime_changed_at,
        "knowledge_books_imported": state.knowledge_books_imported,
        "knowledge_last_updated": state.knowledge_last_updated,
        "last_inspiration_scan": state.last_inspiration_scan,
        "last_audit_run": state.last_audit_run,
        "last_factor_check": state.last_factor_check,
    }


def _dict_to_state(data: dict) -> EvolutionState:
    """从 dict 恢复 EvolutionState。"""
    return EvolutionState(
        version=data.get("version", "1.0.0"),
        created_at=data.get("created_at", ""),
        updated_at=data.get("updated_at", ""),
        total_cycles=data.get("total_cycles", 0),
        successful_improvements=data.get("successful_improvements", 0),
        failed_attempts=data.get("failed_attempts", 0),
        current_cycle=data.get("current_cycle", 0),
        cycle_started_at=data.get("cycle_started_at", ""),
        cycle_phase=data.get("cycle_phase", "idle"),
        weaknesses_found=data.get("weaknesses_found", []),
        active_improvement=data.get("active_improvement"),
        verified_improvements=data.get("verified_improvements", []),
        improvement_history=data.get("improvement_history", []),
        failed_experiments=data.get("failed_experiments", []),
        factor_health_snapshot=data.get("factor_health_snapshot", {}),
        strategy_health_snapshot=data.get("strategy_health_snapshot", {}),
        market_regime=data.get("market_regime", "UNKNOWN"),
        market_regime_changed_at=data.get("market_regime_changed_at", ""),
        knowledge_books_imported=data.get("knowledge_books_imported", 0),
        knowledge_last_updated=data.get("knowledge_last_updated", ""),
        last_inspiration_scan=data.get("last_inspiration_scan", ""),
        last_audit_run=data.get("last_audit_run", ""),
        last_factor_check=data.get("last_factor_check", ""),
    )


# ============================================================
# 预测账本
# ============================================================

@dataclass
class PredictionEntry:
    """单条预测记录。"""
    id: str
    symbol: str
    action: str  # buy / sell / hold
    entry_range: list[float]
    stop_loss: float
    targets: list[float]
    confidence: float
    rationale: str
    technical_score: float
    fundamental_score: float
    sentiment_score: float
    created_at: str
    status: str = "open"  # open / closed / expired
    actual_outcome: str | None = None  # win / loss / breakeven
    actual_return: float | None = None
    closed_at: str | None = None
    review_notes: str | None = None
    source_strategy: str = "unknown"


def load_ledger() -> list[dict]:
    """加载预测账本。"""
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError,):
            pass
    return []


def save_ledger(entries: list[dict]) -> None:
    """保存预测账本。"""
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def record_prediction(entry: dict) -> None:
    """记录一条新预测。"""
    ledger = load_ledger()
    ledger.append(entry)
    save_ledger(ledger)


def update_outcome(prediction_id: str, outcome: str, actual_return: float,
                   notes: str = "") -> None:
    """更新预测结果。"""
    ledger = load_ledger()
    for entry in ledger:
        if entry.get("id") == prediction_id:
            entry["status"] = "closed"
            entry["actual_outcome"] = outcome
            entry["actual_return"] = actual_return
            entry["closed_at"] = datetime.now().isoformat()
            entry["review_notes"] = notes
            break
    save_ledger(ledger)
