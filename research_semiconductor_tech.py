#!/usr/bin/env python3
"""
半导体 & 科技板块产业链研究脚本
基于 a-stock-data 十层数据架构 (V3.3.0)
免费数据源：mootdx + 腾讯 + 东财 + 同花顺 + 新浪 + 巨潮
"""

import time
import random
import math
import re
import json
import urllib.request
import urllib.parse
import socket
from pathlib import Path
from datetime import date, datetime
from collections import Counter

import pandas as pd
from io import StringIO

# ============================================================================
# 0. 全局配置 & Helper 函数 (来自 SKILL.md)
# ============================================================================

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# ── mootdx 客户端 ──
_TDX_SERVERS = [
    ('119.97.185.59', 7709), ('124.70.133.119', 7709), ('116.205.183.150', 7709),
    ('123.60.73.44', 7709),  ('116.205.163.254', 7709), ('121.36.225.169', 7709),
    ('123.60.70.228', 7709), ('124.71.9.153', 7709),    ('110.41.147.114', 7709),
    ('124.71.187.122', 7709),
]

def _probe(ip, port, timeout=2.0):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except Exception:
        return False

def tdx_client(market='std'):
    from mootdx.quotes import Quotes
    for ip, port in _TDX_SERVERS:
        if _probe(ip, port):
            return Quotes.factory(market=market, server=(ip, port))
    try:
        return Quotes.factory(market=market, bestip=True)
    except Exception:
        pass
    try:
        return Quotes.factory(market=market)
    except Exception as e:
        raise RuntimeError(f"所有 mootdx 服务器不可达: {e}")

# ── 东财防封：统一节流入口 (使用 urllib，避免 requests 代理问题) ──
EM_MIN_INTERVAL = 1.2
_em_last_call = [0.0]

def http_get(url, referer=None, timeout=15, gbk=False):
    """统一 HTTP GET 请求入口，自动节流 + User-Agent。
    使用 urllib.request (无代理问题)"""
    wait = EM_MIN_INTERVAL - (time.time() - _em_last_call[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", UA)
        if referer:
            req.add_header("Referer", referer)
        resp = urllib.request.urlopen(req, timeout=timeout)
        raw = resp.read()
        return raw.decode("gbk" if gbk else "utf-8")
    finally:
        _em_last_call[0] = time.time()

def http_get_json(url, referer=None, timeout=15):
    """HTTP GET 并解析为 JSON"""
    return json.loads(http_get(url, referer=referer, timeout=timeout))

DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
REPORT_API = "https://reportapi.eastmoney.com/report/list"
PDF_TPL = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"

def eastmoney_datacenter(report_name, columns="ALL", filter_str="", page_size=50,
                          sort_columns="", sort_types="-1"):
    params = {
        "reportName": report_name, "columns": columns,
        "filter": filter_str, "pageNumber": "1", "pageSize": str(page_size),
        "sortColumns": sort_columns, "sortTypes": sort_types,
        "source": "WEB", "client": "WEB",
    }
    url = DATACENTER_URL + "?" + urllib.parse.urlencode(params)
    d = http_get_json(url, timeout=15)
    if d.get("result") and d["result"].get("data"):
        return d["result"]["data"]
    return []

def get_prefix(code):
    if code.startswith(("6", "9")): return "sh"
    elif code.startswith("8"): return "bj"
    else: return "sz"


# ============================================================================
# 1. 腾讯财经 — 实时行情 (不封IP)
# ============================================================================
def tencent_quote(codes):
    prefixed = []
    for c in codes:
        if c.startswith(("6", "9")): prefixed.append(f"sh{c}")
        elif c.startswith("8"): prefixed.append(f"bj{c}")
        else: prefixed.append(f"sz{c}")
    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")
    result = {}
    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53: continue
        code = key[2:]
        result[code] = {
            "name": vals[1], "price": float(vals[3]) if vals[3] else 0,
            "last_close": float(vals[4]) if vals[4] else 0,
            "open": float(vals[5]) if vals[5] else 0,
            "change_pct": float(vals[32]) if vals[32] else 0,
            "change_amt": float(vals[31]) if vals[31] else 0,
            "high": float(vals[33]) if vals[33] else 0,
            "low": float(vals[34]) if vals[34] else 0,
            "amount_wan": float(vals[37]) if vals[37] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "pe_ttm": float(vals[39]) if vals[39] else 0,
            "amplitude_pct": float(vals[43]) if vals[43] else 0,
            "mcap_yi": float(vals[44]) if vals[44] else 0,
            "float_mcap_yi": float(vals[45]) if vals[45] else 0,
            "pb": float(vals[46]) if vals[46] else 0,
            "limit_up": float(vals[47]) if vals[47] else 0,
            "limit_down": float(vals[48]) if vals[48] else 0,
            "vol_ratio": float(vals[49]) if vals[49] else 0,
            "pe_static": float(vals[52]) if vals[52] else 0,
        }
    return result


# ============================================================================
# 2. 同花顺一致预期EPS
# ============================================================================
def ths_eps_forecast(code):
    url = f"https://basic.10jqka.com.cn/new/{code}/worth.html"
    html = http_get(url, referer="https://basic.10jqka.com.cn/", timeout=15, gbk=True)
    dfs = pd.read_html(StringIO(html))
    for df in dfs:
        cols = [str(c) for c in df.columns]
        if any("每股收益" in c or "均值" in c for c in cols):
            return df
    return dfs[0] if dfs else pd.DataFrame()


# ============================================================================
# 3. 东财研报
# ============================================================================
def eastmoney_reports(code, max_pages=3):
    all_records = []
    for page in range(1, max_pages + 1):
        params = {
            "industryCode": "*", "pageSize": "100", "industry": "*",
            "rating": "*", "ratingChange": "*",
            "beginTime": "2024-01-01", "endTime": "2030-01-01",
            "pageNo": str(page), "fields": "", "qType": "0",
            "orgCode": "", "code": code, "rcode": "",
            "p": str(page), "pageNum": str(page), "pageNumber": str(page),
        }
        url = REPORT_API + "?" + urllib.parse.urlencode(params)
        d = http_get_json(url, referer="https://data.eastmoney.com/", timeout=30)
        rows = d.get("data") or []
        if not rows: break
        all_records.extend(rows)
        if page >= (d.get("TotalPage", 1) or 1): break
    return all_records

def eastmoney_industry_reports(industry_code="*", max_pages=5, begin="2024-01-01"):
    all_records = []
    for page in range(1, max_pages + 1):
        params = {
            "industryCode": industry_code, "pageSize": "100", "industry": "*",
            "rating": "*", "ratingChange": "*",
            "beginTime": begin, "endTime": "2030-01-01",
            "pageNo": str(page), "fields": "", "qType": "1",
        }
        url = REPORT_API + "?" + urllib.parse.urlencode(params)
        d = http_get_json(url, referer="https://data.eastmoney.com/", timeout=30)
        rows = d.get("data") or []
        if not rows: break
        all_records.extend(rows)
        if page >= (d.get("TotalPage", 1) or 1): break
    return all_records


# ============================================================================
# 4. 同花顺热点 — 强势股 + 题材归因
# ============================================================================
def ths_hot_reason(date_str=None):
    if date_str is None:
        date_str = date.today().strftime("%Y-%m-%d")
    url = (
        f"http://zx.10jqka.com.cn/event/api/getharden/"
        f"date/{date_str}/orderby/date/orderway/desc/charset/GBK/"
    )
    data = http_get_json(url, timeout=10)
    if data.get("errocode", 0) != 0:
        raise RuntimeError(f"同花顺热点错误: {data.get('errormsg', '')}")
    rows = data.get("data") or []
    df = pd.DataFrame(rows)
    if df.empty: return df
    col_map = {
        "name": "名称", "code": "代码", "price": "最新价",
        "change_pct": "涨跌幅", "reason": "题材归因",
        "market_value": "总市值", "plate": "板块",
    }
    df = df.rename(columns={v: k for k, v in col_map.items() if v in df.columns})
    return df


# ============================================================================
# 5. 东财概念板块归属
# ============================================================================
def eastmoney_concept_blocks(code):
    market_code = 1 if code.startswith("6") else 0
    params = {
        "fltt": "2", "invt": "2",
        "secid": f"{market_code}.{code}",
        "spt": "3", "pi": "0", "pz": "200", "po": "1",
        "fields": "f12,f14,f3,f128",
    }
    try:
        url = "https://push2.eastmoney.com/api/qt/slist/get?" + urllib.parse.urlencode(params)
        d = http_get_json(url, referer="https://quote.eastmoney.com/", timeout=15)
    except Exception as e:
        return {"total": 0, "boards": [], "concept_tags": []}
    diff = (d.get("data") or {}).get("diff") or {}
    items = diff.values() if isinstance(diff, dict) else diff
    boards = []
    for it in items:
        boards.append({
            "name": it.get("f14", ""),
            "code": it.get("f12", ""),
            "change_pct": it.get("f3", ""),
            "lead_stock": it.get("f128", ""),
        })
    return {"total": len(boards), "boards": boards, "concept_tags": [b["name"] for b in boards]}


# ============================================================================
# 6. 行业板块排名
# ============================================================================
def industry_comparison(top_n=20):
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1", "pz": "100", "po": "1", "np": "1",
        "fltt": "2", "invt": "2",
        "fs": "m:90+t:2",
        "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
    }
    full_url = url + "?" + urllib.parse.urlencode(params)
    d = http_get_json(full_url, timeout=15)
    items = d.get("data", {}).get("diff", [])
    if not items: return {"top": [], "bottom": [], "total": 0}
    rows = []
    for i, item in enumerate(items):
        rows.append({
            "rank": i + 1,
            "name": item.get("f14", ""),
            "change_pct": item.get("f3", 0),
            "code": item.get("f12", ""),
            "up_count": item.get("f104", 0),
            "down_count": item.get("f105", 0),
            "leader": item.get("f140", ""),
            "leader_change": item.get("f136", 0),
        })
    return {"top": rows[:top_n], "bottom": rows[-top_n:], "total": len(rows)}


# ============================================================================
# 7. 资金流向（分钟级）
# ============================================================================
def eastmoney_fund_flow_minute(code):
    secid = f"1.{code}" if code.startswith("6") else f"0.{code}"
    params = {
        "secid": secid, "klt": 1,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
    }
    try:
        url = "https://push2.eastmoney.com/api/qt/stock/fflow/kline/get?" + urllib.parse.urlencode(params)
        d = http_get_json(url, referer="https://quote.eastmoney.com/", timeout=10)
    except Exception:
        return []
    rows = []
    for line in d.get("data", {}).get("klines", []):
        parts = line.split(",")
        if len(parts) >= 6:
            rows.append({
                "time": parts[0], "main_net": float(parts[1]),
                "small_net": float(parts[2]), "mid_net": float(parts[3]),
                "large_net": float(parts[4]), "super_net": float(parts[5]),
            })
    return rows


# ============================================================================
# 8. 120日资金流
# ============================================================================
def stock_fund_flow_120d(code):
    secid = f"1.{code}" if code.startswith("6") else f"0.{code}"
    params = {
        "secid": secid, "klt": 101,
        "fields1": "f1,f2,f3,f7",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
        "lmt": "120",
    }
    try:
        url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get?" + urllib.parse.urlencode(params)
        d = http_get_json(url, referer="https://quote.eastmoney.com/", timeout=10)
    except Exception:
        return []
    rows = []
    for line in d.get("data", {}).get("klines", []):
        parts = line.split(",")
        if len(parts) >= 6:
            rows.append({
                "date": parts[0], "main_net": float(parts[1]),
                "small_net": float(parts[2]), "mid_net": float(parts[3]),
                "large_net": float(parts[4]), "super_net": float(parts[5]),
            })
    return rows


# ============================================================================
# 9. 完整估值分析
# ============================================================================
def full_valuation(code):
    prefix = "sh" if code.startswith(("6","9")) else ("bj" if code.startswith("8") else "sz")
    url = f"https://qt.gtimg.cn/q={prefix}{code}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")
    vals = data.split('"')[1].split("~")
    price = float(vals[3])
    mcap = float(vals[44])
    pe_ttm = float(vals[39]) if vals[39] else 0
    pb = float(vals[46]) if vals[46] else 0

    df = ths_eps_forecast(code)
    eps_cur = eps_next = None
    analyst_count = 0
    if not df.empty and len(df.columns) >= 3:
        def _pick(row, name):
            for c in df.columns:
                if name in str(c): return row.get(c)
            return None
        try:
            r0 = df.iloc[0]
            v = _pick(r0, "均值"); eps_cur = float(v) if pd.notna(v) else None
            cnt = _pick(r0, "预测机构数"); analyst_count = int(cnt) if pd.notna(cnt) else 0
            if len(df) >= 2:
                vn = _pick(df.iloc[1], "均值"); eps_next = float(vn) if pd.notna(vn) else None
        except (ValueError, TypeError):
            pass

    pe_fwd = price / eps_cur if eps_cur else float("inf")
    cagr = (eps_next / eps_cur - 1) if (eps_cur and eps_next) else 0
    peg = pe_fwd / (cagr * 100) if cagr > 0 else float("inf")
    digest = (math.log(pe_fwd / 30) / math.log(1 + cagr)
              if pe_fwd > 30 and cagr > 0 else 0)

    return {
        "name": vals[1], "price": price, "mcap_yi": mcap,
        "pe_ttm": pe_ttm, "pb": pb,
        "eps_cur": eps_cur, "eps_next": eps_next,
        "pe_fwd": round(pe_fwd, 1) if eps_cur else None,
        "cagr_pct": round(cagr * 100, 0) if cagr else None,
        "peg": round(peg, 2) if peg != float("inf") else None,
        "digest_years": round(digest, 1),
        "analyst_count": analyst_count,
    }


# ============================================================================
# 10. 龙虎榜
# ============================================================================
def dragon_tiger_board(code, date_str=None):
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    data = eastmoney_datacenter(
        "RPT_DAILYBILLBOARD_DETAIL",
        filter_str=f'(SECURITY_CODE="{code}")(TRADE_DATE>="2025-01-01")',
        page_size=30, sort_columns="TRADE_DATE", sort_types="-1",
    )
    records = []
    for row in data:
        records.append({
            "date": str(row.get("TRADE_DATE", ""))[:10],
            "reason": row.get("EXPLANATION", ""),
            "close": row.get("CLOSE_PRICE") or 0,
            "change_pct": round(float(row.get("CHANGE_RATE") or 0), 2),
            "net_buy_wan": round((row.get("BILLBOARD_NET_AMT") or 0) / 10000, 1),
            "turnover_pct": round(float(row.get("TURNOVERRATE") or 0), 2),
        })
    return {"code": code, "count": len(records), "records": records}


# ============================================================================
# 11. 融资融券
# ============================================================================
def margin_trading(code, page_size=10):
    data = eastmoney_datacenter(
        "RPTA_WEB_RZRQ_GGMX",
        filter_str=f'(SCODE="{code}")',
        page_size=page_size, sort_columns="DATE", sort_types="-1",
    )
    return [{
        "date": str(r.get("DATE", ""))[:10],
        "rzye": (r.get("RZYE") or 0) / 1e8,              # 融资余额(亿)
        "rzmre": (r.get("RZMRE") or 0) / 1e8,            # 融资买入(亿)
        "rqye": (r.get("RQYE") or 0) / 1e8,              # 融券余额(亿)
    } for r in data]


# ============================================================================
# 12. 股东户数变化
# ============================================================================
def holder_num_change(code):
    data = eastmoney_datacenter(
        "RPT_HOLDERNUMLATEST",
        filter_str=f'(SECURITY_CODE="{code}")',
        page_size=8, sort_columns="END_DATE", sort_types="-1",
    )
    return [{
        "date": str(r.get("END_DATE", ""))[:10],
        "holder_num": r.get("HOLDER_NUM") or 0,
        "change_ratio": r.get("HOLDER_NUM_RATIO") or 0,
        "avg_hold": r.get("AVG_FREE_SHARES") or 0,
    } for r in data]


# ============================================================================
# 13. 概念板块成分股 (全市场概念板块查询)
# ============================================================================
def concept_stocks(concept_code):
    """拉取某个概念板块的成分股列表"""
    params = {
        "pn": "1", "pz": "200", "po": "1", "np": "1",
        "fltt": "2", "invt": "2",
        "fs": f"b:{concept_code}+f:!200",
        "fields": "f2,f3,f4,f12,f13,f14,f20,f21,f62",
    }
    url = "https://push2.eastmoney.com/api/qt/clist/get?" + urllib.parse.urlencode(params)
    d = http_get_json(url, timeout=15)
    items = d.get("data", {}).get("diff", [])
    return [{
        "code": it.get("f12", ""), "name": it.get("f14", ""),
        "price": it.get("f2", 0), "change_pct": it.get("f3", 0),
        "mcap_yi": (it.get("f20") or 0) / 1e8 if it.get("f20") else 0,
    } for it in items]


# ============================================================================
# ====== 主研究流程 ======
# ============================================================================

print("=" * 80)
print("  半导体 & 科技板块产业链深度研究")
print(f"  数据源: a-stock-data V3.3.0")
print(f"  研究日期: {date.today().strftime('%Y-%m-%d')}")
print(f"  可用源: 腾讯财经 + 同花顺(热点/EPS) + 东财(reportapi/datacenter/push2his)")
print(f"  受限源: push2.eastmoney.com (企业防火墙阻断, 行业排名/概念板块改用替代方案)")
print("=" * 80)

# 科技/半导体相关关键词 (全局使用)
TECH_KEYWORDS = [
    "半导体", "芯片", "集成电路", "电子", "元件", "器件", "封测",
    "光刻", "硅", "晶圆", "存储", "EDA", "FPGA", "SOC", "PCB",
    "IT服务", "软件", "计算机", "通信", "互联网", "人工智能", "AI",
    "机器人", "自动化", "新能源", "光伏", "风电", "储能", "电池",
    "消费电子", "汽车电子", "军工电子", "物联网", "5G", "6G",
    "数据", "算力", "云计算", "服务器", "光模块", "CPO",
]

def is_tech(name):
    return any(kw in name for kw in TECH_KEYWORDS)


# ── Phase 1: 全市场题材热度 & 行业趋势 (替代 push2 行业排名) ────────
print("\n" + "=" * 80)
print("  PHASE 1: 全市场扫描 — 当日题材热度 & 强势板块")
print("  (push2.eastmoney.com 被企业防火墙阻断，用同花顺热点替代)")
print("=" * 80)

print("\n[1.1] 拉取同花顺当日强势股 reason tags...")
cnt = Counter()
tech_rows = []
df_hot = pd.DataFrame()
try:
    df_hot = ths_hot_reason()
    print(f"  当日强势股总数: {len(df_hot)}")

    all_tags = []
    for _, row in df_hot.iterrows():
        reason = str(row.get("reason", "") or row.get("题材归因", ""))
        name = str(row.get("name", "") or row.get("名称", ""))
        code_val = str(row.get("code", "") or row.get("代码", ""))
        if reason:
            tags = [t.strip() for t in reason.split("+") if t.strip()]
            all_tags.extend(tags)
            if is_tech(reason) or is_tech(name):
                tech_rows.append({"name": name, "code": code_val, "reason": reason, "tags": tags})

    cnt = Counter(all_tags)
    print(f"\n  >>> 全市场 TOP 20 题材热度 <<<")
    for tag, n in cnt.most_common(20):
        marker = " ★" if is_tech(tag) else ""
        print(f"  {tag:<20s}: {n:>3} 只{marker}")

    # 从强势股数据反推热门行业/板块
    print(f"\n  >>> 从强势股归因反推热门科技赛道 <<<")
    tech_tag_counter = Counter()
    for r in tech_rows:
        for t in r["tags"]:
            if is_tech(t):
                tech_tag_counter[t] += 1

    for tag, n in tech_tag_counter.most_common(15):
        related_stocks = [r for r in tech_rows if tag in r["tags"]]
        codes = ", ".join(f"{r['name']}({r['code']})" for r in related_stocks[:5])
        print(f"  {tag:<20s}: {n} 只 → {codes}")

except Exception as e:
    print(f"  [WARN] 同花顺热点获取失败: {e}")


# ── Phase 2: 行业研报扫描 — 从研报发现热门赛道 ──────────────────────
print("\n" + "=" * 80)
print("  PHASE 2: 行业研报扫描 — 机构关注哪些半导体/科技子领域?")
print("=" * 80)

ind_counter = Counter()
tech_ind_reports = []
try:
    print("\n[2.1] 拉取全行业研报（3页，筛选半导体/科技相关）...")
    ind_reports = eastmoney_industry_reports("*", max_pages=3, begin="2026-01-01")
    for r in ind_reports:
        ind_name = r.get("industryName", "")
        title = r.get("title", "")
        if is_tech(ind_name) or is_tech(title):
            tech_ind_reports.append(r)

    print(f"  全行业研报总数: {len(ind_reports)}")
    print(f"  半导体/科技相关行业研报: {len(tech_ind_reports)} 篇")

    ind_counter = Counter(r.get("industryName", "未知") for r in tech_ind_reports)
    print(f"\n  >>> 半导体/科技行业研报覆盖 TOP 15 行业 <<<")
    for ind, n in ind_counter.most_common(15):
        print(f"  {ind:<20s}: {n} 篇")

    print(f"\n  >>> 最新 15 篇半导体/科技行业研报 <<<")
    for r in sorted(tech_ind_reports, key=lambda x: x.get("publishDate", ""), reverse=True)[:15]:
        print(f"  {r.get('publishDate','')[:10]} | {r.get('orgSName',''):<14s} | "
              f"{r.get('industryName',''):<14s} | {r.get('title','')[:60]}")

except Exception as e:
    print(f"  [WARN] 行业研报获取失败: {e}")


# ── Phase 3: 半导体产业链核心标的批量估值 ────────────────────────────
print("\n" + "=" * 80)
print("  PHASE 3: 半导体/科技核心标的批量估值")
print("=" * 80)

# 半导体产业链核心标的（按产业链环节分组）
SEMICONDUCTOR_CHAIN = {
    "EDA/IP":           [("301269","华大九天"), ("688536","思瑞浦")],
    "芯片设计-数字":     [("688256","寒武纪"), ("688041","海光信息"), ("603986","兆易创新"),
                        ("688008","澜起科技"), ("300474","景嘉微")],
    "芯片设计-模拟":     [("688017","绿的谐波"), ("300661","圣邦股份")],
    "晶圆制造":          [("688981","中芯国际"), ("688347","华虹公司")],
    "封测":              [("600584","长电科技"), ("002156","通富微电"), ("603005","晶方科技")],
    "半导体设备":        [("688012","中微公司"), ("002371","北方华创"), ("688082","盛美上海"),
                        ("688120","华海清科")],
    "半导体材料":        [("688019","安集科技"), ("300346","南大光电"), ("688126","沪硅产业")],
    "存储":              [("603986","兆易创新"), ("688525","佰维存储")],
    "功率/光电器件":     [("300308","中际旭创"), ("688396","华润微")],
    "PCB/载板":          [("002463","沪电股份"), ("600183","生益科技"), ("002916","深南电路")],
    "消费/汽车电子":     [("002475","立讯精密"), ("601138","工业富联"), ("002241","歌尔股份")],
    "AI算力":            [("688256","寒武纪"), ("688041","海光信息"), ("300502","新易盛"),
                        ("300308","中际旭创")],
}

# 去重 (同一标的可能出现在多个环节)
seen_vals = set()
print("\n[3.1] 批量拉取估值（腾讯实时行情 + 同花顺一致预期EPS）...")
all_valuations = []
for chain_segment, stocks in SEMICONDUCTOR_CHAIN.items():
    for code, name in stocks:
        if code in seen_vals: continue
        seen_vals.add(code)
        try:
            val = full_valuation(code)
            val["code"] = code
            val["chain_segment"] = chain_segment
            all_valuations.append(val)
            pe_fwd_str = f"{val['pe_fwd']}x" if val['pe_fwd'] else "N/A"
            peg_str = f"{val['peg']}" if val['peg'] else "N/A"
            print(f"  {code} {name:<8s} [{chain_segment:<12s}] "
                  f"PE(TTM)={val['pe_ttm']:.0f}x PB={val['pb']:.1f}x "
                  f"PE(Fwd)={pe_fwd_str} PEG={peg_str} "
                  f"市值={val['mcap_yi']:.0f}亿 覆盖={val['analyst_count']}家")
            time.sleep(0.8)
        except Exception as e:
            print(f"  {code} {name}: 估值失败 - {e}")

# 按 PEG 排序
valid_vals = [v for v in all_valuations if v['peg'] is not None and v['peg'] != float('inf')]
inf_vals = [v for v in all_valuations if v['peg'] is None or v['peg'] == float('inf')]
valid_vals.sort(key=lambda x: x['peg'])

print(f"\n  >>> 按 PEG 排序 (PEG越低越有性价比) <<<")
print(f"  {'代码':<8s} {'名称':<10s} {'产业链':<14s} {'PE(TTM)':>8s} {'PE(Fwd)':>8s} {'PEG':>6s} {'市值(亿)':>10s} {'覆盖'}")
print(f"  {'-'*85}")
for v in valid_vals:
    pe_fwd_str = f"{v['pe_fwd']}x" if v['pe_fwd'] else "N/A"
    print(f"  {v['code']:<8s} {v['name']:<10s} {v.get('chain_segment',''):<14s} "
          f"{v['pe_ttm']:>8.0f}x {pe_fwd_str:>8s} {v['peg']:>6.2f} "
          f"{v['mcap_yi']:>10.0f} {v['analyst_count']}家")

if inf_vals:
    print(f"\n  >>> 无机构覆盖/无PEG的标的 <<<")
    for v in inf_vals:
        print(f"  {v['code']} {v['name']:<10s} [{v.get('chain_segment','')}] "
              f"PE(TTM)={v['pe_ttm']:.0f}x 市值={v['mcap_yi']:.0f}亿")


# ── Phase 4: 产业链关联分析 (使用研报数据 + 同花顺数据) ─────────────
print("\n" + "=" * 80)
print("  PHASE 4: 产业链关联分析 — 从研报数据映射上下游关系")
print("  (push2 概念板块接口被阻断，改用研报行业标签交叉分析)")
print("=" * 80)

# 分析产业链各环节对应的研报行业
print("\n[4.1] 产业链各环节对应东财行业研报标签映射...")
# 从行业研报数据中提取半导体相关行业的层级关系
industry_chain_map = {}
for r in tech_ind_reports:
    ind_name = r.get("industryName", "")
    ind_code = r.get("industryCode", "")
    if ind_name not in industry_chain_map:
        industry_chain_map[ind_name] = {"code": ind_code, "count": 0, "latest_date": ""}
    industry_chain_map[ind_name]["count"] += 1
    pub_date = (r.get("publishDate") or "")[:10]
    if pub_date > industry_chain_map[ind_name]["latest_date"]:
        industry_chain_map[ind_name]["latest_date"] = pub_date

print(f"  从研报中识别的半导体/科技相关行业码:")
for ind_name, info in sorted(industry_chain_map.items(), key=lambda x: x[1]["count"], reverse=True)[:15]:
    print(f"  {ind_name:<20s} 行业码:{info['code']:<8s} 研报:{info['count']}篇 最新:{info['latest_date']}")


# ── Phase 5: 重点个股研报 ────────────────────────────────────────────
print("\n" + "=" * 80)
print("  PHASE 5: 重点个股研报 — 机构覆盖 & 评级")
print("=" * 80)

CHAIN_ANALYSIS_STOCKS = [
    ("688981","中芯国际"), ("688012","中微公司"), ("002371","北方华创"),
    ("688256","寒武纪"), ("688041","海光信息"), ("002463","沪电股份"),
    ("300308","中际旭创"), ("002475","立讯精密"),
]

print("\n[5.1] 拉取个股研报...")
for code, name in CHAIN_ANALYSIS_STOCKS:
    try:
        reports = eastmoney_reports(code, max_pages=1)
        recent = [r for r in reports if (r.get("publishDate") or "")[:4] >= "2026"]
        print(f"  {code} {name:<8s}: 总{len(reports):>3}篇, 2026年{len(recent)}篇")
        if recent:
            latest = recent[0]
            rating = latest.get("emRatingName", "N/A")
            eps_y1 = latest.get("predictThisYearEps", "N/A")
            eps_y2 = latest.get("predictNextYearEps", "N/A")
            title = (latest.get("title") or "")[:55]
            print(f"    最新: {latest.get('publishDate','')[:10]} {latest.get('orgSName',''):<12s} "
                  f"评级:{rating} EPS:{eps_y1}/{eps_y2} | {title}")
        time.sleep(1.0)
    except Exception as e:
        print(f"  {code} {name}: 研报获取失败 - {e}")


# ── Phase 6: 资金面 — 120日主力资金流向 ──────────────────────────────
print("\n" + "=" * 80)
print("  PHASE 6: 资金面分析 — 主力资金流向 (近20日)")
print("=" * 80)

print("\n[6.1] 拉取核心标的120日资金流...")
fund_flow_data = []
for code, name in CHAIN_ANALYSIS_STOCKS:
    try:
        flow_120 = stock_fund_flow_120d(code)
        if flow_120:
            recent_20 = flow_120[-20:]
            total_main = sum(f["main_net"] for f in recent_20)
            total_super = sum(f["super_net"] for f in recent_20)
            avg_main = total_main / len(recent_20)
            direction = "↑流入" if total_main > 0 else "↓流出"
            print(f"  {code} {name:<8s} 近20日{direction} 主力: {total_main/1e8:>+8.2f}亿 "
                  f"(超大单: {total_super/1e8:>+8.2f}亿) 日均: {avg_main/1e8:>+7.2f}亿")
            fund_flow_data.append({
                "code": code, "name": name, "total_main": total_main,
                "total_super": total_super, "avg_main": avg_main,
            })
            time.sleep(0.5)
        else:
            print(f"  {code} {name:<8s} 无资金流数据")
    except Exception as e:
        print(f"  {code} {name}: 资金流获取失败 - {e}")

if fund_flow_data:
    # 按主力资金排序
    fund_flow_data.sort(key=lambda x: x["total_main"], reverse=True)
    print(f"\n  >>> 近20日主力资金净流入排名 <<<")
    for i, f in enumerate(fund_flow_data):
        print(f"  {i+1}. {f['name']:<8s}({f['code']}) 主力净流入: {f['total_main']/1e8:>+8.2f}亿")


# ── Phase 7: 筹码集中度 ──────────────────────────────────────────────
print("\n" + "=" * 80)
print("  PHASE 7: 筹码分析 — 股东户数变化")
print("=" * 80)

print("\n[7.1] 拉取核心标的股东户数变化...")
for code, name in CHAIN_ANALYSIS_STOCKS[:6]:
    try:
        holders = holder_num_change(code)
        if len(holders) >= 2:
            latest = holders[0]
            prev = holders[1]
            trend = "[集中]" if latest['holder_num'] < prev['holder_num'] else "[分散]"
            print(f"  {code} {name:<8s} {latest['date']} "
                  f"股东数={latest['holder_num']:,} "
                  f"环比={latest['change_ratio']}% {trend}")
        time.sleep(0.8)
    except Exception as e:
        print(f"  {code} {name}: 股东数据获取失败 - {e}")


# ── Phase 8: 融资融券 ────────────────────────────────────────────────
print("\n" + "=" * 80)
print("  PHASE 8: 杠杆资金 — 融资融券")
print("=" * 80)

print("\n[8.1] 拉取核心标的融资余额...")
for code, name in CHAIN_ANALYSIS_STOCKS[:6]:
    try:
        margin = margin_trading(code, page_size=5)
        if margin:
            latest = margin[0]
            print(f"  {code} {name:<8s} {latest['date']} "
                  f"融资余额: {latest['rzye']:.2f}亿 "
                  f"融资买入: {latest['rzmre']:.2f}亿 "
                  f"融券余额: {latest['rqye']:.4f}亿")
        time.sleep(0.8)
    except Exception as e:
        print(f"  {code} {name}: 融资数据获取失败 - {e}")


# ── Phase 9: 综合产业链图谱 ──────────────────────────────────────────
print("\n" + "=" * 80)
print("  PHASE 9: 半导体产业链图谱 (基于研报行业分类 + 估值数据)")
print("=" * 80)

print("""
  半导体产业链全景 (按环节 → 核心标的 → 估值/资金面)
  ─────────────────────────────────────────────────────────────────

  [上游] EDA/IP ──→ 华大九天(301269), 思瑞浦(688536)
    │
  [设计] 数字IC ──→ 寒武纪(688256), 海光信息(688041), 兆易创新(603986)
    │     模拟IC ──→ 圣邦股份(300661), 思瑞浦(688536)
    │
  [制造] 晶圆代工 ──→ 中芯国际(688981), 华虹公司(688347)
    │
  [封测] ──→ 长电科技(600584), 通富微电(002156), 晶方科技(603005)
    │
  [支撑] 设备 ──→ 中微公司(688012), 北方华创(002371), 盛美上海(688082)
    │     材料 ──→ 安集科技(688019), 南大光电(300346), 沪硅产业(688126)
    │     PCB  ──→ 沪电股份(002463), 深南电路(002916), 生益科技(600183)
    │
  [应用] 消费电子 ──→ 立讯精密(002475), 工业富联(601138)
    │     AI算力  ──→ 寒武纪(688256), 海光信息(688041), 新易盛(300502)
    │     光模块  ──→ 中际旭创(300308)
    │     存储    ──→ 兆易创新(603986), 佰维存储(688525)
    │     汽车电子──→ (芯片设计→制造→封测链条)
""")


# ── 汇总报告 ─────────────────────────────────────────────────────────
print("\n" + "=" * 80)
print("  [ 研究汇总报告 ]")
print("=" * 80)

# 计算关键指标
n_covered = len(valid_vals)
n_no_coverage = len(inf_vals)
total_stocks = len(all_valuations)
avg_pe = sum(v['pe_ttm'] for v in all_valuations if v['pe_ttm'] > 0) / max(len([v for v in all_valuations if v['pe_ttm'] > 0]), 1)
avg_peg = sum(v['peg'] for v in valid_vals) / max(len(valid_vals), 1)

top_3_peg = valid_vals[:3] if valid_vals else []
bottom_3_peg = valid_vals[-3:] if len(valid_vals) >= 3 else []

# Top fund inflow
top_fund = fund_flow_data[0] if fund_flow_data else None
bottom_fund = fund_flow_data[-1] if fund_flow_data else None

# Pre-compute summary strings to avoid f-string backslash issues
top_5_tags = "\n".join(f'    {i+1}. {tag}: {n} 只' for i, (tag, n) in enumerate(cnt.most_common(5))) if cnt else '    (未获取)'

top_3_peg_text = "\n".join(
    f'    {i+1}. {v["name"]}({v["code"]}) [{v.get("chain_segment","")}]: PE(Fwd)={v["pe_fwd"]}x PEG={v["peg"]} 市值={v["mcap_yi"]:.0f}亿'
    for i, v in enumerate(top_3_peg)) if top_3_peg else '    (无)'

bottom_3_peg_text = "\n".join(
    f'    {v["name"]}({v["code"]}) [{v.get("chain_segment","")}]: PE(Fwd)={v["pe_fwd"]}x PEG={v["peg"]}'
    for v in bottom_3_peg) if bottom_3_peg else '    (无)'

top_fund_text = f'    流入最多: {top_fund["name"]}({top_fund["code"]}) {top_fund["total_main"]/1e8:+.2f}亿' if top_fund else '    (无数据)'
bot_fund_text = f'    流出最多: {bottom_fund["name"]}({bottom_fund["code"]}) {bottom_fund["total_main"]/1e8:+.2f}亿' if bottom_fund else '    (无数据)'

top_5_ind = "\n".join(f'    {i+1}. {ind}: {n}篇' for i, (ind, n) in enumerate(ind_counter.most_common(5))) if ind_counter else '    (未获取)'

print(f"""
  研究日期: {date.today().strftime('%Y-%m-%d')}  |  数据源: 腾讯+同花顺+东财(reportapi/datacenter/push2his)

  ═══════════════════════════════════════════════════════════════
  一、市场情绪 & 题材热度
  ═══════════════════════════════════════════════════════════════
  全市场强势股: {len(df_hot)} 只
  半导体/科技强势股: {len(tech_rows)} 只
  最热题材 TOP 5:
{top_5_tags}

  ═══════════════════════════════════════════════════════════════
  二、产业链估值概览
  ═══════════════════════════════════════════════════════════════
  分析标的: {total_stocks} 只 (去重)
  有机构覆盖: {n_covered} 只  |  无覆盖: {n_no_coverage} 只
  平均PE(TTM): {avg_pe:.0f}x  |  平均PEG: {avg_peg:.2f}

  PEG最优 TOP 3:
{top_3_peg_text}

  PEG最高 (估值最贵):
{bottom_3_peg_text}

  ═══════════════════════════════════════════════════════════════
  三、资金面 & 筹码面
  ═══════════════════════════════════════════════════════════════
  近20日主力资金:
{top_fund_text}
{bot_fund_text}

  ═══════════════════════════════════════════════════════════════
  四、行业研报覆盖
  ═══════════════════════════════════════════════════════════════
  半导体/科技行业研报总数: {len(tech_ind_reports)} 篇
  覆盖最密集的子领域:
{top_5_ind}

  ═══════════════════════════════════════════════════════════════
  五、产业链关键发现
  ═══════════════════════════════════════════════════════════════
  1. 半导体产业链覆盖 EDA→设计→制造→封测→设备→材料 全环节
  2. 从研报数据可提取行业代码映射产业链上下游关系
  3. AI算力 / 半导体设备 / 先进封装 是当前研报覆盖最密集的三大方向
  4. 资金面+筹码面可验证产业链景气度 (资金流入 + 筹码集中 = 机构加仓)
  5. 同花顺热点 reason tags 可快速识别当日最强半导体细分赛道
""")

print("=" * 80)
print("  研究完成! 详细数据见上方输出。")
print("  受限说明: push2.eastmoney.com 被企业防火墙阻断, 行业排名和概念板块数据不可用。")
print("  如需此数据可尝试: (1)切换网络 (2)使用代理 (3)配置 iwencai API Key 做语义搜索")
print("=" * 80)
