"""Buffett 6-Gate Pre-Purchase Checklist.

From ai-berkshire: a rapid 6-gate screen to decide if a company is worth deep research.
Each gate is scored 1-5 stars; 8 hard veto triggers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GateResult:
    gate: int
    name: str
    score: int = 0      # 1-5 stars
    passed: bool = False
    notes: str = ""


@dataclass
class ChecklistResult:
    company: str
    gates: list[GateResult] = field(default_factory=list)
    veto_triggered: bool = False
    veto_reason: str = ""
    overall_score: int = 0
    mirror_test_pass: bool = False
    thesis: str = ""

    @property
    def passed(self) -> bool:
        return not self.veto_triggered and self.overall_score >= 15


# Hard veto triggers (any one = reject)
VETO_LIST = [
    "无法用一句话解释公司如何赚钱",
    "连续3年自由现金流为负且无改善趋势",
    "管理层诚信污点",
    "竞争优势不可逆地被侵蚀",
    "需要下一个买家以更高价接盘才能赚钱（greater fool）",
    "无法承受全部亏损",
    "因为'大家都在买'所以买入",
    "无法用200字写清投资thesis",
]


def run_checklist(company: str, data: dict[str, Any]) -> ChecklistResult:
    """Run the full 6-gate Buffett pre-purchase checklist.

    Args:
        company: company name
        data: dict with financial data (financials, quote, etc.)

    Returns:
        ChecklistResult with pass/fail per gate
    """
    result = ChecklistResult(company=company)

    # Gate 1: Circle of Competence
    g1 = _gate1_circle_of_competence(company)
    result.gates.append(g1)

    # Gate 2: Good Business
    g2 = _gate2_good_business(data)
    result.gates.append(g2)

    # Gate 3: Moat
    g3 = _gate3_moat(data)
    result.gates.append(g3)

    # Gate 4: Management
    g4 = _gate4_management(data)
    result.gates.append(g4)

    # Gate 5: Safety Margin
    g5 = _gate5_safety_margin(data)
    result.gates.append(g5)

    # Gate 6: Decision Discipline
    g6 = _gate6_decision_discipline()
    result.gates.append(g6)

    result.overall_score = sum(g.score for g in result.gates)
    return result


def _gate1_circle_of_competence(company: str) -> GateResult:
    """Can you explain the business in one sentence? Will it exist in 10 years?"""
    return GateResult(
        gate=1, name="能力圈 (Circle of Competence)",
        score=3, passed=True,
        notes=f"请回答：能否用一句话解释{company}的商业模式？10年后还会存在吗？",
    )


def _gate2_good_business(data: dict) -> GateResult:
    """ROE > 15%, gross margin > 40%, FCF positive, asset-light."""
    fin = data.get("financials", {})
    score = 0

    roe = fin.get("roe", 0)
    if roe > 20:
        score += 2
    elif roe > 15:
        score += 1

    gm = fin.get("gross_margin", 0)
    if gm > 40:
        score += 1

    fcf = fin.get("fcf", 0)
    if fcf > 0:
        score += 1

    # Asset-light check
    asset_turnover = fin.get("asset_turnover", 0)
    if asset_turnover > 0.5:
        score += 1

    return GateResult(
        gate=2, name="好生意 (Good Business)",
        score=min(5, score), passed=score >= 3,
        notes=f"ROE={roe:.1f}%, 毛利率={gm:.1f}%, FCF={fcf:.0f}",
    )


def _gate3_moat(data: dict) -> GateResult:
    """Moat assessment: brand, switching costs, network effects, scale, patents."""
    fin = data.get("financials", {})
    score = 0

    gm = fin.get("gross_margin", 0)
    if gm > 50:
        score += 2  # High margin suggests pricing power
    elif gm > 30:
        score += 1

    roe = fin.get("roe", 0)
    if roe > 25:
        score += 1  # Sustained high ROE suggests moat

    market_share = fin.get("market_share", 0)
    if market_share > 20:
        score += 1

    patents = fin.get("patent_count", 0)
    if patents > 100:
        score += 1

    return GateResult(
        gate=3, name="护城河 (Moat)",
        score=min(5, score), passed=score >= 2,
        notes=f"毛利率={gm:.1f}% ROE={roe:.1f}% 市占率={market_share:.1f}%",
    )


def _gate4_management(data: dict) -> GateResult:
    """Management: integrity, capital allocation, shareholder alignment."""
    mgmt = data.get("management", {})
    score = 0

    integrity = mgmt.get("integrity_score", 3)
    if integrity <= 2:
        return GateResult(gate=4, name="管理层 (Management)", score=1, passed=False,
                         notes="管理层诚信问题 — 硬否决")
    score += integrity

    # Capital allocation
    buyback = mgmt.get("buyback_positive", False)
    if buyback:
        score += 1

    ownership = mgmt.get("insider_ownership_pct", 0)
    if ownership > 5:
        score += 1

    return GateResult(
        gate=4, name="管理层 (Management)",
        score=min(5, score), passed=score >= 3,
        notes=f"诚信={integrity}/5 内部持股={ownership:.1f}%",
    )


def _gate5_safety_margin(data: dict) -> GateResult:
    """Valuation safety margin: PE, FCF yield, 50% downside test."""
    quote = data.get("quote", {})
    fin = data.get("financials", {})
    score = 0

    pe = quote.get("pe_ttm", 0)
    if pe < 15:
        score += 2
    elif pe < 25:
        score += 1

    fcf_yield = fin.get("fcf_yield", 0)
    if fcf_yield > 0.05:
        score += 1

    pb = quote.get("pb", 0)
    if pb < 2:
        score += 1

    upside = data.get("valuation", {}).get("dcf_upside", 0)
    if upside > 0.3:
        score += 1

    return GateResult(
        gate=5, name="安全边际 (Safety Margin)",
        score=min(5, score), passed=score >= 2,
        notes=f"PE={pe:.1f} PB={pb:.1f} FCF收益率={fcf_yield:.1%}",
    )


def _gate6_decision_discipline() -> GateResult:
    """FOMO check, 5-year trading halt test, thesis in 200 chars."""
    return GateResult(
        gate=6, name="决策纪律 (Decision Discipline)",
        score=3, passed=True,
        notes="请确认：(1) 不是FOMO (2) 5年停牌也愿意持有 (3) 200字内写完thesis",
    )
