"""Quality factors — Piotroski F-Score, Beneish M-Score, accounting red flags.

These are the quantitative quality checks from the value investing framework.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from mystrategy.factors.base import BaseFactor, FactorMeta


class FScore(BaseFactor):
    """Piotroski F-Score (0-9): profitability + leverage/liquidity + operating efficiency."""

    meta = FactorMeta(
        name="f_score",
        category="quality",
        display_name="Piotroski F-Score",
        description="9-point fundamental quality score",
    )

    def compute(self, data: dict[str, Any]) -> dict[str, float]:
        """Compute F-Score from financial data.

        Args:
            data: must contain 3 years of financials with:
                - net_income, total_assets, operating_cash_flow (current + prior year)
                - long_term_debt, current_assets, current_liabilities (current + prior year)
                - shares_outstanding (current + prior year)
                - gross_margin, asset_turnover (current + prior year)
        """
        fin = data.get("financials", {})
        score = 0

        # 1. ROA > 0
        ni = fin.get("net_income", 0)
        ta = fin.get("total_assets", 1)
        score += 1 if ni > 0 and ta > 0 else 0

        # 2. Operating cash flow > 0
        ocf = fin.get("operating_cash_flow", 0)
        score += 1 if ocf > 0 else 0

        # 3. ROA increasing
        ni_prev = fin.get("net_income_prev", ni)
        ta_prev = fin.get("total_assets_prev", ta)
        roa = ni / ta if ta > 0 else 0
        roa_prev = ni_prev / ta_prev if ta_prev > 0 else 0
        score += 1 if roa > roa_prev else 0

        # 4. OCF > Net Income (quality of earnings)
        score += 1 if ocf > ni else 0

        # 5. Long-term debt decreasing
        ltd = fin.get("long_term_debt", 0)
        ltd_prev = fin.get("long_term_debt_prev", ltd + 1)
        score += 1 if ltd < ltd_prev else 0

        # 6. Current ratio improving
        ca = fin.get("current_assets", 0)
        cl = fin.get("current_liabilities", 1)
        ca_prev = fin.get("current_assets_prev", ca)
        cl_prev = fin.get("current_liabilities_prev", cl)
        cr = ca / cl if cl > 0 else 0
        cr_prev = ca_prev / cl_prev if cl_prev > 0 else 0
        score += 1 if cr > cr_prev else 0

        # 7. No share dilution
        shares = fin.get("shares_outstanding", 1)
        shares_prev = fin.get("shares_outstanding_prev", shares)
        score += 1 if shares <= shares_prev else 0

        # 8. Gross margin improving
        gm = fin.get("gross_margin", 0)
        gm_prev = fin.get("gross_margin_prev", gm - 1)
        score += 1 if gm > gm_prev else 0

        # 9. Asset turnover improving
        at = fin.get("asset_turnover", 0)
        at_prev = fin.get("asset_turnover_prev", at - 1)
        score += 1 if at > at_prev else 0

        return {
            "f_score": float(score),
            "f_score_pct": score / 9.0,
        }


class MScore(BaseFactor):
    """Beneish M-Score: earnings manipulation detection.

    M-Score > -2.22 suggests manipulation.
    """

    meta = FactorMeta(
        name="m_score",
        category="quality",
        display_name="Beneish M-Score",
        description="8-variable earnings manipulation detection model",
        thresholds={"m_score": -2.22},
        higher_is_better=False,
    )

    def compute(self, data: dict[str, Any]) -> dict[str, float]:
        fin = data.get("financials", {})
        prev = data.get("financials_prev", {})

        try:
            # DSRI: Days Sales in Receivables Index
            receivables = fin.get("receivables", 0)
            rev = fin.get("revenue", 1)
            receivables_prev = prev.get("receivables", receivables)
            rev_prev = prev.get("revenue", rev)
            dsri = (receivables / rev) / (receivables_prev / rev_prev) if receivables_prev * rev > 0 else 1.0

            # GMI: Gross Margin Index
            gm = fin.get("gross_margin", 0)
            gm_prev = prev.get("gross_margin", gm + 0.001)
            gmi = gm_prev / gm if gm > 0 else 1.0

            # AQI: Asset Quality Index
            ta = fin.get("total_assets", 0)
            ca = fin.get("current_assets", 0)
            nppe = fin.get("ppe_net", 0)
            aqi_num = 1 - (ca + nppe) / ta if ta > 0 else 0
            ta_prev = prev.get("total_assets", ta + 1)
            ca_prev = prev.get("current_assets", ca)
            nppe_prev = prev.get("ppe_net", nppe)
            aqi_den = 1 - (ca_prev + nppe_prev) / ta_prev if ta_prev > 0 else 1
            aqi = aqi_num / aqi_den if aqi_den > 0 else 1.0

            # SGI: Sales Growth Index
            sgi = rev / rev_prev if rev_prev > 0 else 1.0

            # DEPI: Depreciation Index
            dep = fin.get("depreciation", 1)
            dep_prev = prev.get("depreciation", dep)
            depi = (dep_prev / (dep_prev + nppe_prev if nppe_prev > 0 else 1)) / \
                   (dep / (dep + nppe if nppe > 0 else 1)) if dep * (dep_prev + nppe_prev) > 0 else 1.0

            # SGAI: SGA Expense Index
            sga = fin.get("sga_expense", 0)
            sga_prev = prev.get("sga_expense", sga)
            sgai = (sga / rev) / (sga_prev / rev_prev) if sga_prev * rev > 0 else 1.0

            # LVGI: Leverage Index
            ltd = fin.get("long_term_debt", 0)
            cl = fin.get("current_liabilities", 0)
            ltd_prev = prev.get("long_term_debt", ltd)
            cl_prev = prev.get("current_liabilities", cl)
            lev = (ltd + cl) / ta if ta > 0 else 0
            lev_prev = (ltd_prev + cl_prev) / ta_prev if ta_prev > 0 else 0
            lvgi = lev / lev_prev if lev_prev > 0 else 1.0

            # TATA: Total Accruals to Total Assets
            ni = fin.get("net_income", 0)
            ocf = fin.get("operating_cash_flow", 0)
            tata = (ni - ocf) / ta if ta > 0 else 0

            # M-Score formula
            m_score = (
                -4.84
                + 0.920 * dsri
                + 0.528 * gmi
                + 0.404 * aqi
                + 0.892 * sgi
                + 0.115 * depi
                - 0.172 * sgai
                - 0.327 * lvgi
                + 4.679 * tata
            )

            return {
                "m_score": m_score,
                "m_score_warning": 1 if m_score > -2.22 else 0,
                "dsri": dsri, "gmi": gmi, "aqi": aqi,
                "sgi": sgi, "depi": depi, "sgai": sgai,
                "lvgi": lvgi, "tata": tata,
            }

        except (ZeroDivisionError, TypeError):
            return {"m_score": 0.0, "m_score_warning": 0}


class RedFlags(BaseFactor):
    """11 accounting red flags check."""

    meta = FactorMeta(
        name="red_flags",
        category="quality",
        display_name="会计红旗",
        description="11 accounting red flag indicators",
        thresholds={"red_flag_count": 3},
        higher_is_better=False,
    )

    def compute(self, data: dict[str, Any]) -> dict[str, float]:
        fin = data.get("financials", {})
        flags = 0

        # 1. Revenue growth slowing but receivables growing faster
        rev_growth = fin.get("revenue_growth", 0)
        ar_growth = fin.get("receivables_growth", 0)
        if rev_growth > 0 and ar_growth > rev_growth * 1.5:
            flags += 1

        # 2. Inventory growing faster than revenue
        inv_growth = fin.get("inventory_growth", 0)
        if inv_growth > max(rev_growth * 2, 20):
            flags += 1

        # 3. OCF significantly below net income
        ni = fin.get("net_income", 1)
        ocf = fin.get("operating_cash_flow", 0)
        if ocf / ni < 0.5 if ni > 0 else ocf < ni:
            flags += 1

        # 4. Gross margin declining 3 consecutive periods
        if fin.get("gm_declining_streak", 0) >= 3:
            flags += 1

        # 5. Sudden increase in capitalized expenses
        if fin.get("capex_spike", 0) > 50:
            flags += 1

        # 6. Goodwill / total assets > 50%
        goodwill = fin.get("goodwill", 0)
        ta = fin.get("total_assets", 1)
        if goodwill / ta > 0.5:
            flags += 1

        # 7. Related party transactions > 10% of revenue
        if fin.get("related_party_revenue_pct", 0) > 10:
            flags += 1

        # 8. Auditor changed in last year
        if fin.get("auditor_changed", 0):
            flags += 1

        # 9. Non-standard audit opinion
        if fin.get("non_standard_audit", 0):
            flags += 1

        # 10. Insider selling > buying
        if fin.get("insider_sell_ratio", 0) > 0.7:
            flags += 1

        # 11. Revenue concentration (top 5 > 50%)
        if fin.get("top5_customer_pct", 0) > 50:
            flags += 1

        return {
            "red_flag_count": float(flags),
            "red_flag_warning": 1 if flags >= 3 else 0,
        }
