"""Investment Thesis Tracker.

From ai-berkshire: post-purchase discipline system.
Tracks whether investment thesis remains intact via assumption checking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Assumption:
    """A single thesis assumption to track."""
    description: str
    verification_method: str
    check_frequency: str = "quarterly"  # daily, weekly, quarterly, annually
    status: str = "green"  # green, yellow, red, black
    last_checked: str = ""
    evidence: str = ""


@dataclass
class ThesisTracker:
    """An investment thesis with assumptions and red lines."""

    company: str
    ticker: str = ""
    thesis_200char: str = ""
    assumptions: list[Assumption] = field(default_factory=list)
    red_lines: list[str] = field(default_factory=list)
    valuation_anchor: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    health_score: int = 10

    # Duan Yongping's 3 sell rules
    SELL_RULES = [
        "发现自己错了",
        "公司基本面变了",
        "找到了更好的机会",
    ]

    def check_assumptions(self, latest_data: dict[str, Any]) -> int:
        """Check all assumptions against latest data.

        Returns:
            Health score (1-10):
            9-10: All intact, thesis stronger → consider adding
            7-8: Core intact, minor weakening → hold
            5-6: 1-2 damaged, core unchanged → hold but alert
            3-4: Multiple damaged, thesis shaky → consider reducing
            1-2: Red line triggered OR core broken → strongly advise sell
        """
        deductions = 0
        self.updated_at = datetime.now().strftime("%Y-%m-%d")

        for assumption in self.assumptions:
            # Check if red line triggered
            for red_line in self.red_lines:
                if self._check_red_line(red_line, latest_data):
                    deductions += 5  # Red line = instant severe penalty
                    assumption.status = "black"

            # Simple heuristic checks based on assumption description
            if "revenue" in assumption.description.lower():
                rev_growth = latest_data.get("financials", {}).get("revenue_growth", 0)
                if rev_growth < -5:
                    assumption.status = "red"
                    deductions += 3
                elif rev_growth < 0:
                    assumption.status = "yellow"
                    deductions += 1
                else:
                    assumption.status = "green"

            elif "margin" in assumption.description.lower():
                gm = latest_data.get("financials", {}).get("gross_margin", 0)
                gm_prev = latest_data.get("financials", {}).get("gross_margin_prev", gm)
                if gm < gm_prev - 3:
                    assumption.status = "red"
                    deductions += 2
                elif gm < gm_prev:
                    assumption.status = "yellow"
                    deductions += 1
                else:
                    assumption.status = "green"

            elif "management" in assumption.description.lower():
                integrity = latest_data.get("management", {}).get("integrity_flag", False)
                if not integrity:
                    assumption.status = "green"
                else:
                    assumption.status = "red"
                    deductions += 3

            elif "competitive" in assumption.description.lower():
                market_share = latest_data.get("financials", {}).get("market_share", 0)
                ms_prev = latest_data.get("financials", {}).get("market_share_prev", market_share + 1)
                if market_share < ms_prev - 1:
                    assumption.status = "red"
                    deductions += 2
                elif market_share < ms_prev:
                    assumption.status = "yellow"
                    deductions += 1
                else:
                    assumption.status = "green"

        self.health_score = max(1, 10 - deductions)
        return self.health_score

    def _check_red_line(self, red_line: str, data: dict) -> bool:
        """Check if a red line has been triggered."""
        # Simple keyword matching against latest data
        fin = data.get("financials", {})
        mgmt = data.get("management", {})

        if "FCF转负" in red_line and fin.get("fcf", 1) < 0:
            return True
        if "ROE持续恶化" in red_line and fin.get("roe", 15) < 5:
            return True
        if "管理层负面" in red_line and mgmt.get("negative_event", False):
            return True
        if "监管" in red_line and data.get("regulatory_risk", 0) > 0.5:
            return True
        return False

    def get_recommendation(self) -> str:
        """Get action recommendation based on health score."""
        if self.health_score >= 9:
            return "ADD — 所有假设完好，可以考虑加仓"
        elif self.health_score >= 7:
            return "HOLD — 核心逻辑完好，继续持有"
        elif self.health_score >= 5:
            return "HOLD_ALERT — 部分假设受损，密切观察"
        elif self.health_score >= 3:
            return "REDUCE — 多项假设受损，考虑减仓"
        else:
            return "SELL — 红线触发或核心假设破灭，坚定卖出"


def create_thesis(company: str, thesis: str, red_lines: list[str],
                  assumptions: list[dict]) -> ThesisTracker:
    """Create a new investment thesis.

    Args:
        company: company name
        thesis: 200-char investment thesis
        red_lines: list of red line descriptions
        assumptions: list of {description, verification_method, check_frequency} dicts
    """
    return ThesisTracker(
        company=company,
        thesis_200char=thesis[:200],
        red_lines=red_lines,
        assumptions=[
            Assumption(
                description=a["description"],
                verification_method=a.get("verification_method", ""),
                check_frequency=a.get("check_frequency", "quarterly"),
            )
            for a in assumptions
        ],
        created_at=datetime.now().strftime("%Y-%m-%d"),
        updated_at=datetime.now().strftime("%Y-%m-%d"),
        health_score=10,
    )
