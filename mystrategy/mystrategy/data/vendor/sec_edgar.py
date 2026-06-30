"""SEC EDGAR data vendor.

Covers: company filings (10-K, 10-Q, 8-K), financial data (XBRL facts),
CIK lookup.

Source: sec.gov EDGAR API
Rate limit: 10 req/s (SEC requirement). No API key needed.
"""

from __future__ import annotations

import json as _json
import re as _re
import time
import logging
from typing import Any

import requests as _requests

UA = "mycompany@example.com"  # SEC requires User-Agent identifying the caller

logger = logging.getLogger(__name__)

_last_call = 0.0


def _throttle():
    """SEC requires max 10 req/s."""
    global _last_call
    elapsed = time.time() - _last_call
    if elapsed < 0.1:
        time.sleep(0.1 - elapsed)
    _last_call = time.time()


# ---------------------------------------------------------------------------
# CIK lookup
# ---------------------------------------------------------------------------

def ticker_to_cik(ticker: str) -> str:
    """Convert ticker to SEC CIK number."""
    url = "https://www.sec.gov/files/company_tickers.json"
    _throttle()
    try:
        r = _requests.get(url, headers={"User-Agent": UA}, timeout=10)
        data = r.json()
        for item in data.values():
            if item.get("ticker", "").upper() == ticker.upper():
                return str(item["cik_str"]).zfill(10)
    except Exception:
        pass
    return ""


def cik_to_ticker(cik: str) -> str:
    """Convert CIK to ticker."""
    url = "https://www.sec.gov/files/company_tickers.json"
    _throttle()
    try:
        r = _requests.get(url, headers={"User-Agent": UA}, timeout=10)
        data = r.json()
        cik_clean = str(cik).lstrip("0")
        for item in data.values():
            if str(item["cik_str"]) == cik_clean:
                return item.get("ticker", "")
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Company submissions (filing history)
# ---------------------------------------------------------------------------

def submissions(cik: str) -> dict:
    """Get company filing history from SEC EDGAR.

    Returns full submissions data including recent filings list.
    """
    cik_clean = str(cik).lstrip("0")
    url = f"https://data.sec.gov/submissions/CIK{cik_clean}.json"
    _throttle()
    try:
        r = _requests.get(url, headers={"User-Agent": UA}, timeout=15)
        return r.json() or {}
    except Exception:
        return {}


def recent_filings(cik: str, form_types: list[str] | None = None,
                   count: int = 20) -> list[dict]:
    """Get recent filings for a company.

    Args:
        cik: SEC CIK number
        form_types: filter by form type (e.g., ['10-K', '10-Q', '8-K'])
        count: max filings to return

    Returns:
        [{accessionNumber, form, filingDate, reportDate, primaryDocument, ...}]
    """
    data = submissions(cik)
    filings = data.get("filings", {}).get("recent", {}) or {}
    if not filings:
        return []

    result = []
    acc_numbers = filings.get("accessionNumber", [])
    forms = filings.get("form", [])
    dates = filings.get("filingDate", [])
    report_dates = filings.get("reportDate", [])
    docs = filings.get("primaryDocument", [])

    for i in range(min(len(acc_numbers), count * 3)):
        if form_types and forms[i] not in form_types:
            continue
        result.append({
            "accession_number": acc_numbers[i],
            "form": forms[i],
            "filing_date": dates[i],
            "report_date": report_dates[i] if i < len(report_dates) else "",
            "primary_document": docs[i] if i < len(docs) else "",
            "url": f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_numbers[i].replace('-', '')}/{docs[i]}" if i < len(docs) else "",
        })
        if len(result) >= count:
            break
    return result


# ---------------------------------------------------------------------------
# Company facts (XBRL financial data)
# ---------------------------------------------------------------------------

def company_facts(cik: str) -> dict:
    """Get all XBRL-tagged financial facts for a company.

    Returns structured GAAP/IFRS financial data with 503+ metrics.
    Uses the Company Facts API (XBRL taxonomy).
    """
    cik_clean = str(cik).lstrip("0")
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_clean}.json"
    _throttle()
    try:
        r = _requests.get(url, headers={"User-Agent": UA}, timeout=30)
        return r.json() or {}
    except Exception:
        return {}


def gaap_fact(cik: str, fact_name: str, unit: str = "USD") -> list[dict]:
    """Get a specific GAAP fact's history.

    Args:
        cik: company CIK
        fact_name: XBRL fact name (e.g., 'Revenues', 'NetIncomeLoss', 'Assets')
        unit: 'USD', 'shares', 'USDPerShare', etc.

    Returns:
        [{end, val, fy, fp, form, filed}] sorted by end date descending
    """
    facts = company_facts(cik)
    us_gaap = facts.get("facts", {}).get("us-gaap", {}) or {}
    fact_data = us_gaap.get(fact_name, {}) or {}
    units = fact_data.get("units", {}) or {}
    entries = units.get(unit, [])

    result = []
    for entry in entries[:20]:
        result.append({
            "end": entry.get("end", ""),
            "val": entry.get("val", 0),
            "fy": entry.get("fy", 0),
            "fp": entry.get("fp", ""),
            "form": entry.get("form", ""),
            "filed": entry.get("filed", ""),
        })
    return sorted(result, key=lambda x: x["end"], reverse=True)


def key_financials(cik: str) -> dict:
    """Extract key financial metrics from XBRL facts.

    Returns: {revenue, net_income, total_assets, total_equity,
              operating_cash_flow, eps_basic, eps_diluted, shares_outstanding,
              long_term_debt, goodwill}
    """
    fact_names = {
        "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
        "Revenues": "revenue_alt",
        "NetIncomeLoss": "net_income",
        "Assets": "total_assets",
        "StockholdersEquity": "total_equity",
        "NetCashProvidedByUsedInOperatingActivities": "operating_cash_flow",
        "EarningsPerShareBasic": "eps_basic",
        "EarningsPerShareDiluted": "eps_diluted",
        "CommonStockSharesOutstanding": "shares_outstanding",
        "LongTermDebt": "long_term_debt",
        "Goodwill": "goodwill",
    }

    facts = company_facts(cik)
    us_gaap = facts.get("facts", {}).get("us-gaap", {}) or {}
    result = {}

    for xbrl_name, key in fact_names.items():
        fact_data = us_gaap.get(xbrl_name, {}) or {}
        units = fact_data.get("units", {}) or {}
        entries = units.get("USD", units.get("shares", units.get("USDPerShare", [])))
        if entries:
            result[key] = entries[0].get("val", 0)

    return result


# ---------------------------------------------------------------------------
# Filing document download
# ---------------------------------------------------------------------------

def filing_document(url: str) -> str:
    """Download a filing document (raw HTML or text)."""
    _throttle()
    try:
        r = _requests.get(url, headers={"User-Agent": UA}, timeout=30)
        return r.text
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def health_check() -> bool:
    """Quick connectivity test."""
    try:
        _throttle()
        r = _requests.get("https://www.sec.gov/files/company_tickers.json",
                          headers={"User-Agent": UA}, timeout=5)
        return r.status_code == 200
    except Exception:
        return False
