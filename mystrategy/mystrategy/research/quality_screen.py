"""7 Hard-Indicator Quality Screen.

From ai-berkshire: rapidly eliminate non-first-class companies.
7 indicators, each pass/fail, with 3 exemption rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QualityScreenResult:
    company: str
    indicators: list[dict] = field(default_factory=list)
    passed_count: int = 0
    total_count: int = 7
    exemption_applied: str = ""
    verdict: str = ""  # "PASS", "FAIL", "EXEMPTED"


def run_quality_screen(company: str, data: dict[str, Any]) -> QualityScreenResult:
    """Run the 7-indicator quality screen.

    Args:
        company: company name
        data: dict with 'financials' containing multi-year data

    Returns:
        QualityScreenResult with pass/fail per indicator
    """
    fin = data.get("financials", {})
    result = QualityScreenResult(company=company)
    indicators = []

    # 1. 10-year average ROE >= 8%
    roe_10yr = fin.get("roe_10yr_avg", 0)
    ind1 = {"name": "10年ROE均值", "value": roe_10yr, "threshold": ">=8%",
            "passed": roe_10yr >= 8, "exempted": False}
    # Exemption A: listed < 10 years AND gross margin > 30% AND OCF positive
    if not ind1["passed"] and fin.get("listed_years", 10) < 10 and \
       fin.get("gross_margin", 0) > 30 and fin.get("ocf_last_2yr", 0) > 0:
        ind1["exempted"] = True
        ind1["passed"] = True
        result.exemption_applied = "A (战略投入期)"
    indicators.append(ind1)

    # 2. 5-year cumulative FCF >= 0
    fcf_5yr = fin.get("fcf_5yr_cumulative", -1)
    ind2 = {"name": "5年累计自由现金流", "value": fcf_5yr, "threshold": ">=0",
            "passed": fcf_5yr >= 0, "exempted": False}
    indicators.append(ind2)

    # 3. Interest coverage EBIT/Interest >= 2x
    ic = fin.get("interest_coverage", 0)
    ind3 = {"name": "利息保障倍数", "value": ic, "threshold": ">=2x",
            "passed": ic >= 2, "exempted": False}
    # Not applicable: banks, insurance
    if fin.get("is_financial", False):
        ind3["exempted"] = True
        ind3["passed"] = True
    indicators.append(ind3)

    # 4. Long-term gross margin >= 15%
    gm = fin.get("gross_margin_lt", 0)
    ind4 = {"name": "长期毛利率", "value": gm, "threshold": ">=15%",
            "passed": gm >= 15, "exempted": False}
    # Exemption C: high-turnover thin margin (ROE>20% + OCF/NP>1.0)
    if not ind4["passed"] and fin.get("roe", 0) > 20 and \
       fin.get("ocf_np_ratio", 0) > 1.0:
        ind4["exempted"] = True
        ind4["passed"] = True
        result.exemption_applied = "C (高周转薄利)"
    indicators.append(ind4)

    # 5. OCF / Net Profit (5yr avg) >= 0.7
    ocf_ratio = fin.get("ocf_np_5yr_avg", 0)
    ind5 = {"name": "经营现金流/净利润", "value": ocf_ratio, "threshold": ">=0.7",
            "passed": ocf_ratio >= 0.7, "exempted": False}
    indicators.append(ind5)

    # 6. Long-term net profit margin >= 5%
    npm = fin.get("net_margin_lt", 0)
    ind6 = {"name": "长期净利率", "value": npm, "threshold": ">=5%",
            "passed": npm >= 5, "exempted": False}
    # Exemption B: gross margin >30% AND last 2yr net margin >=5% or rising
    if not ind6["passed"] and fin.get("gross_margin", 0) > 30 and \
       (fin.get("net_margin_2yr", 0) >= 5 or fin.get("net_margin_rising", False)):
        ind6["exempted"] = True
        ind6["passed"] = True
        result.exemption_applied = result.exemption_applied or "B (主动低净利率)"
    # Exemption C: also applies
    if not ind6["passed"] and fin.get("roe", 0) > 20 and \
       fin.get("ocf_np_ratio", 0) > 1.0:
        ind6["exempted"] = True
        ind6["passed"] = True
    indicators.append(ind6)

    # 7. 5-year total share dilution (non-M&A) <= 20%
    dilution = fin.get("share_dilution_5yr", 0)
    ind7 = {"name": "5年股本稀释", "value": dilution, "threshold": "<=20%",
            "passed": dilution <= 20, "exempted": False}
    indicators.append(ind7)

    result.indicators = indicators
    result.passed_count = sum(1 for i in indicators if i["passed"])

    if result.passed_count == 7:
        result.verdict = "PASS — 全部通过，需进一步深度研究"
    elif result.passed_count >= 5:
        result.verdict = "PASS — 大部分通过，需关注未通过项"
    else:
        result.verdict = "FAIL — 未通过基本质量门槛"

    return result
