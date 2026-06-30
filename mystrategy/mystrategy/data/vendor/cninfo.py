"""Cninfo (巨潮资讯) data vendor.

Covers: full-text announcement search for Shanghai/Shenzhen/Beijing markets,
investor relations Q&A (互动易).

Source: cninfo.com.cn
Rate limit: Minimal (官方披露平台).
"""

from __future__ import annotations

import re as _re
from datetime import datetime
from typing import Any

import requests as _requests

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


# ---------------------------------------------------------------------------
# Announcement search
# ---------------------------------------------------------------------------

def _org_id(code: str) -> str:
    """Map 6-digit code to cninfo org ID."""
    code = str(code).strip()
    if code.startswith("6"):
        return f"gssh0{code}"
    elif code.startswith("8") or code.startswith("4"):
        return f"gsbj0{code}"
    else:
        return f"gssz0{code}"


def _cninfo_ts_to_date(ts: Any) -> str:
    """Convert timestamp to date string."""
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d")
        except Exception:
            pass
    return str(ts)[:10] if ts else ""


def announcements(code: str, page_size: int = 10,
                  keyword: str = "", category: str = "") -> list[dict]:
    """Search company announcements (全文检索).

    Args:
        code: 6-digit stock code
        page_size: max results (default 10)
        keyword: optional search keyword (title + full text)
        category: optional category filter

    Returns:
        [{title, type, date, url, announcement_id}]
    """
    url = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
    org = _org_id(code)
    payload = {
        "stock": f"{code},{org}",
        "tabName": "fulltext",
        "pageSize": str(page_size),
        "pageNum": "1",
        "column": "",
        "category": category,
        "plate": "",
        "seDate": "",
        "searchkey": keyword,
        "secid": "",
        "sortName": "",
        "sortType": "",
        "isHLtitle": "true",
    }
    headers = {
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://www.cninfo.com.cn/new/disclosure",
        "Origin": "https://www.cninfo.com.cn",
    }
    try:
        r = _requests.post(url, data=payload, headers=headers, timeout=15)
        d = r.json()
    except Exception:
        return []

    rows = []
    for item in d.get("announcements", []) or []:
        rows.append({
            "title": item.get("announcementTitle", ""),
            "type": item.get("announcementTypeName", ""),
            "date": _cninfo_ts_to_date(item.get("announcementTime")),
            "url": f"https://static.cninfo.com.cn/{item.get('adjunctUrl', '')}",
            "announcement_id": item.get("announcementId", ""),
            "sec_name": item.get("secName", ""),
        })
    return rows


def announcement_detail(announcement_id: str) -> dict:
    """Get announcement full text content."""
    url = "https://www.cninfo.com.cn/new/announcement/bulletinDetail"
    params = {"announcementId": announcement_id}
    headers = {
        "User-Agent": UA,
        "Referer": "https://www.cninfo.com.cn/new/disclosure",
    }
    try:
        r = _requests.get(url, params=params, headers=headers, timeout=15)
        return r.json() or {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Investor Relations Q&A (互动易)
# ---------------------------------------------------------------------------

def irm_qa(code: str, page_size: int = 20) -> list[dict]:
    """Get investor relations Q&A (互动易问答).

    Returns: [{question, answer, question_time, answer_time}]
    """
    url = "https://irm.cninfo.com.cn/ircs/search/question"
    params = {
        "stockCode": str(code).strip(),
        "pageSize": str(page_size),
        "pageNum": "1",
    }
    headers = {
        "User-Agent": UA,
        "Referer": "https://irm.cninfo.com.cn/",
    }
    try:
        r = _requests.get(url, params=params, headers=headers, timeout=15)
        d = r.json()
        rows = []
        for item in d.get("list", []) or []:
            rows.append({
                "question": item.get("questionContent", ""),
                "answer": item.get("answerContent", ""),
                "question_time": item.get("questionTime", ""),
                "answer_time": item.get("answerTime", ""),
                "company_name": item.get("companyShortName", ""),
            })
        return rows
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def health_check() -> bool:
    """Quick connectivity test."""
    try:
        r = _requests.get("https://www.cninfo.com.cn/new/disclosure",
                          headers={"User-Agent": UA}, timeout=5)
        return r.status_code == 200
    except Exception:
        return False
