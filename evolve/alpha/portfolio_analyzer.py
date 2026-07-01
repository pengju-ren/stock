"""
Portfolio Analyzer — 用进化引擎的策略分析用户真实持仓。

输入: 用户持仓列表 + 实时行情
输出: 逐标的买入/持有/卖出建议 + 置信度 + 理由
"""

import json, os, sys
import numpy as np
import pandas as pd
from datetime import datetime

EVOLVE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOCK_ROOT = os.path.join(os.path.dirname(EVOLVE_ROOT), "project", "stock-analyzer")
sys.path.insert(0, STOCK_ROOT)


def analyze_portfolio(holdings: list[dict], live_quotes: list[dict] | None = None):
    """Run all 4 active strategies against each holding.

    Returns: [{code, name, type, signals: {strategy_name: signal}, consensus, recommendation}]
    """
    results = []

    for h in holdings:
        code = h["code"]
        name = h["name"]
        htype = h.get("type", "stock")

        signals = {}

        # Strategy 1: CAN SLIM (growth breakout)
        cs_signal = _check_can_slim(code, live_quotes)
        signals["can_slim"] = cs_signal

        # Strategy 2: Dual Momentum (trend)
        dm_signal = _check_dual_momentum(code, live_quotes)
        signals["dual_momentum"] = dm_signal

        # Strategy 3: ETF Rotation (sector momentum)
        etf_signal = _check_etf_rotation(code, h, live_quotes)
        signals["etf_rotation"] = etf_signal

        # Strategy 4: Alpha Composite (voting)
        ac_signal = _check_alpha_composite(code, signals)
        signals["alpha_composite"] = ac_signal

        # Consensus
        buy_votes = sum(1 for s in signals.values() if s.get("action") == "BUY")
        sell_votes = sum(1 for s in signals.values() if s.get("action") == "SELL")
        hold_votes = sum(1 for s in signals.values() if s.get("action") == "HOLD")

        if buy_votes >= 3:
            action, confidence = "加仓", 0.80
        elif buy_votes >= 2:
            action, confidence = "持有偏多", 0.65
        elif sell_votes >= 3:
            action, confidence = "减仓", 0.80
        elif sell_votes >= 2:
            action, confidence = "持有偏空", 0.60
        else:
            action, confidence = "持有", 0.50

        results.append({
            "code": code, "name": name, "type": htype,
            "signals": signals,
            "votes": {"BUY": buy_votes, "SELL": sell_votes, "HOLD": hold_votes},
            "action": action, "confidence": confidence,
            "sector": h.get("sector", ""),
        })

    return results


def _check_can_slim(code, quotes):
    """CAN SLIM check using live data."""
    if quotes is None:
        return {"action": "HOLD", "reason": "无数据", "confidence": 0.5}

    for q in quotes:
        q_code = str(q.get("code", "")).replace(".0", "")
        if q_code == str(code).replace(".0", ""):
            chg = float(q.get("change_pct", 0))
            pe_str = q.get("pe", "N/A")

            score = 0
            reasons = []

            # C: Recent price change
            if chg > 0:
                score += 1
                reasons.append(f"当日涨{chg}%")

            # A: PE reasonable
            try:
                pe = float(pe_str)
                if 0 < pe < 100:
                    score += 1
                    reasons.append(f"PE={pe:.1f}合理")
                elif pe <= 0:
                    score += 0
                    reasons.append("PE为负")
                else:
                    reasons.append(f"PE={pe:.1f}偏高")
            except ValueError:
                pass

            # N: Price level
            price = float(q.get("price", 0))
            if price > 5:  # Not penny stock
                score += 1

            if score >= 2:
                return {"action": "BUY", "reason": "; ".join(reasons),
                        "confidence": 0.5 + score * 0.1, "score": score}
            elif score >= 1:
                return {"action": "HOLD", "reason": "; ".join(reasons),
                        "confidence": 0.5, "score": score}
            else:
                return {"action": "SELL", "reason": "CAN SLIM不满足",
                        "confidence": 0.6, "score": score}

    return {"action": "HOLD", "reason": "无报价", "confidence": 0.5}


def _check_dual_momentum(code, quotes):
    """Dual Momentum — simplified check with live data."""
    if quotes is None:
        return {"action": "HOLD", "reason": "无数据", "confidence": 0.5}

    for q in quotes:
        if str(q.get("code", "")).replace(".0", "") == str(code).replace(".0", ""):
            chg = float(q.get("change_pct", 0))
            price = float(q.get("price", 0))

            if chg > 1:
                return {"action": "BUY", "reason": f"动量强劲+{chg}%",
                        "confidence": min(0.85, 0.5 + abs(chg) / 10)}
            elif chg > -1:
                return {"action": "HOLD", "reason": f"动量中性{chg:+.1f}%",
                        "confidence": 0.5}
            else:
                return {"action": "SELL", "reason": f"动量转负{chg}%",
                        "confidence": 0.6}

    return {"action": "HOLD", "reason": "无报价", "confidence": 0.5}


def _check_etf_rotation(code, holding, quotes):
    """ETF Rotation — check if the sector is in a leading position."""
    # Simplified: ETFs that are up today are likely in leading sectors
    if holding.get("type") == "ETF" and quotes:
        for q in quotes:
            if str(q.get("code", "")).replace(".0", "") == str(code).replace(".0", ""):
                chg = float(q.get("change_pct", 0))
                if chg > 2:
                    return {"action": "BUY", "reason": f"板块领涨+{chg}%",
                            "confidence": 0.7}
                elif chg > 0:
                    return {"action": "HOLD", "reason": f"板块中性{chg:+.2f}%",
                            "confidence": 0.55}
                else:
                    return {"action": "SELL", "reason": f"板块转弱{chg}%",
                            "confidence": 0.6}
    return {"action": "HOLD", "reason": "非ETF或无数据", "confidence": 0.5}


def _check_alpha_composite(code, signals):
    """Alpha Composite — voting result."""
    buy_votes = sum(1 for s in signals.values() if s.get("action") == "BUY")
    sell_votes = sum(1 for s in signals.values() if s.get("action") == "SELL")

    if buy_votes >= 2:
        return {"action": "BUY", "reason": f"{buy_votes}/3策略看多",
                "confidence": 0.5 + buy_votes * 0.1}
    elif sell_votes >= 2:
        return {"action": "SELL", "reason": f"{sell_votes}/3策略看空",
                "confidence": 0.5 + sell_votes * 0.1}
    else:
        return {"action": "HOLD", "reason": "策略分歧", "confidence": 0.5}


def print_report(analysis_results: list[dict]):
    """Pretty print the portfolio analysis."""
    print("\n" + "=" * 90)
    print(f"  PORTFOLIO ANALYSIS — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 90)

    # Group by action
    buy_group = [r for r in analysis_results if "加仓" in r["action"] or "偏多" in r["action"]]
    hold_group = [r for r in analysis_results if "持有" in r["action"] and "偏" not in r["action"]]
    sell_group = [r for r in analysis_results if "减仓" in r["action"] or "偏空" in r["action"]]

    print(f"\n  Portfolio: {len(analysis_results)} holdings")
    print(f"  BUY signals: {len(buy_group)} | HOLD: {len(hold_group)} | SELL: {len(sell_group)}")

    print(f"\n  {'Code':10s} {'Name':18s} {'Type':6s} {'Action':10s} {'Conf':>5s}  {'Votes(B/S/H)':12s}  {'Sector'}")
    print("  " + "-" * 85)
    for r in analysis_results:
        v = r["votes"]
        print(f"  {r['code']:10s} {r['name']:18s} {r['type']:6s} {r['action']:10s} "
              f"{r['confidence']:.0%}   {v['BUY']}/{v['SELL']}/{v['HOLD']}         {r.get('sector','')}")

    print(f"\n  --- Sector Summary ---")
    sectors = {}
    for r in analysis_results:
        sec = r.get("sector", "unknown")
        if sec not in sectors:
            sectors[sec] = {"total": 0, "buy": 0, "sell": 0}
        sectors[sec]["total"] += 1
        if "加仓" in r["action"] or "偏多" in r["action"]:
            sectors[sec]["buy"] += 1
        elif "减仓" in r["action"] or "偏空" in r["action"]:
            sectors[sec]["sell"] += 1

    for sec, stats in sorted(sectors.items()):
        bar = "▓" * stats["buy"] + "░" * (stats["total"] - stats["buy"] - stats["sell"]) + "▒" * stats["sell"]
        print(f"  {sec:15s} [{bar:10s}] {stats['buy']}B/{stats['total']-stats['buy']-stats['sell']}H/{stats['sell']}S")


def save_report(analysis_results, path=None):
    if path is None:
        path = os.path.join(EVOLVE_ROOT, "reports", f"portfolio_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(analysis_results, f, ensure_ascii=False, indent=2, default=str)
    return path


def run():
    """Run portfolio analysis using user's 20 holdings."""
    holdings = [
        {"code": "513120", "name": "港股创新药ETF", "type": "ETF", "sector": "创新药"},
        {"code": "512880", "name": "证券ETF", "type": "ETF", "sector": "金融"},
        {"code": "159851", "name": "金融科技ETF", "type": "ETF", "sector": "金融"},
        {"code": "159530", "name": "机器人ETF", "type": "ETF", "sector": "科技成长"},
        {"code": "159870", "name": "化工ETF", "type": "ETF", "sector": "周期资源"},
        {"code": "06855", "name": "亚盛医药-B", "type": "HK", "sector": "创新药"},
        {"code": "00700", "name": "腾讯控股", "type": "HK", "sector": "互联网"},
        {"code": "01772", "name": "赣锋锂业", "type": "HK", "sector": "周期资源"},
        {"code": "513130", "name": "恒生科技ETF", "type": "ETF", "sector": "科技成长"},
        {"code": "03690", "name": "美团-W", "type": "HK", "sector": "互联网"},
        {"code": "09688", "name": "再鼎医药", "type": "HK", "sector": "创新药"},
        {"code": "159876", "name": "有色ETF", "type": "ETF", "sector": "周期资源"},
        {"code": "603799", "name": "华友钴业", "type": "A", "sector": "周期资源"},
        {"code": "159981", "name": "能源化工ETF", "type": "ETF", "sector": "周期资源"},
        {"code": "588000", "name": "科创50ETF", "type": "ETF", "sector": "科技成长"},
        {"code": "688981", "name": "中芯国际", "type": "A", "sector": "科技成长"},
        {"code": "510880", "name": "红利ETF", "type": "ETF", "sector": "防御"},
        {"code": "515790", "name": "光伏ETF", "type": "ETF", "sector": "新能源"},
        {"code": "159941", "name": "纳指ETF", "type": "ETF", "sector": "海外"},
        {"code": "300373", "name": "扬杰科技", "type": "A", "sector": "科技成长"},
    ]

    # Load live quotes
    quotes_path = os.path.join(EVOLVE_ROOT, "reports", "live_quotes.json")
    quotes = None
    if os.path.exists(quotes_path):
        with open(quotes_path, encoding="utf-8") as f:
            quotes = json.load(f)

    results = analyze_portfolio(holdings, quotes)
    print_report(results)
    save_report(results)
    return results


if __name__ == "__main__":
    run()
