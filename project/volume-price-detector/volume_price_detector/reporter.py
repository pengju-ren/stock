"""结果输出 — 终端表格 / Markdown / JSON 三种格式。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from volume_price_detector.models import ScanResult, Signal, SignalType

if TYPE_CHECKING:
    from collections.abc import Iterable


# ═══════════════════════════════════════════════════════════════
#  终端输出（带颜色）
# ═══════════════════════════════════════════════════════════════

class TermColor:
    """ANSI 颜色码。"""
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def _signal_emoji(s: Signal) -> str:
    return "🔴 卖" if s.signal_type == SignalType.SELL else "🟢 买"


def _risk_color(level: str) -> tuple[str, str]:
    colors = {
        "critical": (TermColor.RED + TermColor.BOLD, TermColor.RESET),
        "high": (TermColor.RED, TermColor.RESET),
        "medium": (TermColor.YELLOW, TermColor.RESET),
        "low": (TermColor.DIM, TermColor.RESET),
    }
    return colors.get(level, ("", ""))


def print_result(result: ScanResult, days: int | None = None,
                 sell_only: bool = False, buy_only: bool = False) -> None:
    """终端格式化输出单个股票的扫描结果。"""
    C = TermColor

    # ── 标题 ──
    name_str = f" - {result.name}" if result.name else ""
    print(f"\n{C.BOLD}{C.CYAN}╔══════════════════════════════════════════════════════╗{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}║{C.RESET}  {C.BOLD}{result.code}{name_str}  [{result.market}股] {C.RESET}")
    print(f"{C.BOLD}{C.CYAN}╚══════════════════════════════════════════════════════╝{C.RESET}")

    # ── 基本信息 ──
    trend_label = {"uptrend": "📈 上升趋势", "downtrend": "📉 下跌趋势",
                   "rangebound": "📊 震荡", "unknown": "❓ 未知"}
    pos_label = {"high": "🔺 高位", "low": "🔻 低位", "mid": "➖ 中位", "unknown": "❓"}

    print(f"  最新价: {C.BOLD}¥{result.latest_price:.2f}{C.RESET}  "
          f"({result.latest_date})  "
          f"{trend_label.get(result.trend, result.trend)}  "
          f"{pos_label.get(result.position, result.position)}")

    # ── 信号列表 ──
    signals = result.signals
    if days:
        signals = result.recent_signals(days)

    if sell_only:
        signals = [s for s in signals if s.signal_type == SignalType.SELL]
    elif buy_only:
        signals = [s for s in signals if s.signal_type == SignalType.BUY]
    else:
        # 默认: 卖点在前，买点在后
        signals = sorted(signals, key=lambda s: (
            0 if s.signal_type == SignalType.SELL else 1,
            -(s.confidence or 0),
        ))

    if not signals:
        print(f"\n  {C.GREEN}✅ 近期未检测到量价信号{C.RESET}")
    else:
        print(f"\n  {C.BOLD}📋 量价信号 ({len(signals)} 条):{C.RESET}\n")
        # 表头
        print(f"  {'日期':<12} {'类型':<6} {'信号名称':<20} {'价格':<10} {'置信度':<8} {'风险':<8}")
        print(f"  {'─'*12} {'─'*6} {'─'*20} {'─'*10} {'─'*8} {'─'*8}")

        for s in signals:
            tag = _signal_emoji(s)
            color_start, color_end = ("", "")
            if s.signal_type == SignalType.SELL and s.risk_level:
                color_start, color_end = _risk_color(s.risk_level.value)

            risk_str = s.risk_level.value.upper() if s.risk_level else "-"

            print(
                f"  {s.date:<12} {tag:<6} "
                f"{color_start}{s.name:<20}{color_end} "
                f"¥{s.price:<9.2f} "
                f"{s.confidence:.0%}  {'':<3}"
                f"{color_start}{risk_str:<8}{color_end}"
            )

            # 描述
            if s.description:
                desc = s.description[:120]
                print(f"  {'':12} {'':6} {C.DIM}{desc}{C.RESET}")

    # ── 风险汇总 ──
    if result.sell_signals:
        r = result.risk_summary
        print(f"\n  {C.BOLD}🔍 风险汇总:{C.RESET}  "
              f"{C.RED}严重 {r['critical']}{C.RESET}  "
              f"{C.YELLOW}高 {r['high']}{C.RESET}  "
              f"中 {r['medium']}  低 {r['low']}")
        print(f"  {result.risk_verdict}")

    print()


def print_batch_summary(results: list[ScanResult], top_n: int = 20) -> None:
    """批量扫描结果摘要表格。"""
    C = TermColor

    print(f"\n{C.BOLD}{C.CYAN}╔══════════════════════════════════════════════════════════════╗{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}║{C.RESET}  量价关系批量扫描结果 {C.RESET}")
    print(f"{C.BOLD}{C.CYAN}╚══════════════════════════════════════════════════════════════╝{C.RESET}")

    # 按风险排序
    def risk_score(r: ScanResult) -> int:
        rs = r.risk_summary
        return rs["critical"] * 100 + rs["high"] * 10 + rs["medium"] * 1

    sorted_results = sorted(results, key=risk_score, reverse=True)

    # 有信号的在前
    with_signals = [r for r in sorted_results if r.signals]
    without_signals = [r for r in sorted_results if not r.signals]

    if not with_signals:
        print(f"\n  {C.GREEN}扫描 {len(results)} 只股票，均未检测到显著量价信号{C.RESET}\n")
        return

    print(f"\n  {C.BOLD}发现 {len(with_signals)} 只有信号 / 共 {len(results)} 只{C.RESET}")
    print(f"\n  {'代码':<8} {'名称':<10} {'最新价':<10} {'趋势':<10} {'卖点':<25} {'买点':<12} {'风险'}")
    print(f"  {'─'*8} {'─'*10} {'─'*10} {'─'*10} {'─'*25} {'─'*12} {'─'*20}")

    for r in with_signals[:top_n]:
        name = r.name[:8] if r.name else ""
        trend_short = {"uptrend": "📈升", "downtrend": "📉跌",
                       "rangebound": "📊震", "unknown": "?"}.get(r.trend, "?")

        rsum = r.risk_summary
        sell_summary = f"C{rsum['critical']} H{rsum['high']} M{rsum['medium']}"
        buy_count = len(r.buy_signals)

        risk_bar = ""
        if rsum["critical"] > 0:
            risk_bar = C.RED + "⚠ 严重" + C.RESET
        elif rsum["high"] >= 2:
            risk_bar = C.RED + "🔴 高" + C.RESET
        elif rsum["high"] >= 1:
            risk_bar = C.YELLOW + "🟡 中" + C.RESET
        elif rsum["medium"] >= 2:
            risk_bar = "🔵 关注"
        else:
            risk_bar = C.GREEN + "✅ 低" + C.RESET

        print(
            f"  {r.code:<8} {name:<10} ¥{r.latest_price:<9.2f} "
            f"{trend_short:<10} {sell_summary:<25} {buy_count:<12} {risk_bar}"
        )

    if len(with_signals) > top_n:
        print(f"  ... 还有 {len(with_signals) - top_n} 只有信号未显示")

    print()


# ═══════════════════════════════════════════════════════════════
#  Markdown 输出
# ═══════════════════════════════════════════════════════════════

def to_markdown(result: ScanResult, days: int | None = None) -> str:
    """生成 Markdown 格式报告。"""
    lines = []

    name_str = f" - {result.name}" if result.name else ""
    lines.append(f"## {result.code}{name_str} 量价分析")
    lines.append("")
    lines.append(f"- **市场**: {result.market}股")
    lines.append(f"- **最新价**: ¥{result.latest_price:.2f} ({result.latest_date})")
    trend_cn = {"uptrend": "📈 上升", "downtrend": "📉 下跌",
                "rangebound": "📊 震荡", "unknown": "未知"}
    pos_cn = {"high": "🔺 高位", "low": "🔻 低位", "mid": "➖ 中位", "unknown": "未知"}
    lines.append(f"- **趋势**: {trend_cn.get(result.trend, result.trend)}")
    lines.append(f"- **位置**: {pos_cn.get(result.position, result.position)}")
    lines.append("")

    signals = result.signals
    if days:
        signals = result.recent_signals(days)

    if not signals:
        lines.append("✅ *近期未检测到量价信号*")
    else:
        lines.append(f"### 📋 量价信号 ({len(signals)} 条)")
        lines.append("")
        lines.append("| 日期 | 类型 | 信号 | 价格 | 置信度 | 风险 |")
        lines.append("|------|------|------|------|--------|------|")

        for s in signals:
            emoji = "🔴" if s.signal_type == SignalType.SELL else "🟢"
            risk_str = s.risk_level.value.upper() if s.risk_level else "-"
            lines.append(
                f"| {s.date} | {emoji} | {s.name} | ¥{s.price:.2f} | "
                f"{s.confidence:.0%} | {risk_str} |"
            )

            if s.description:
                lines.append(f"| | | *{s.description[:100]}* | | | |")

        lines.append("")

    if result.sell_signals:
        r = result.risk_summary
        lines.append(f"### 🔍 风险汇总")
        lines.append(f"- 严重: {r['critical']}  |  高: {r['high']}  |  中: {r['medium']}  |  低: {r['low']}")
        lines.append(f"- **{result.risk_verdict}**")
        lines.append("")

    if result.buy_signals:
        lines.append(f"### 🟢 买点信号 ({len(result.buy_signals)} 条)")
        for s in result.buy_signals[:5]:
            lines.append(f"- [{s.date}] **{s.name}** @ ¥{s.price:.2f} ({s.confidence:.0%})")
        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
#  JSON 输出
# ═══════════════════════════════════════════════════════════════

def to_json(result: ScanResult, days: int | None = None) -> str:
    """生成 JSON 格式输出。"""
    signals = result.signals
    if days:
        signals = result.recent_signals(days)

    data = {
        "code": result.code,
        "name": result.name,
        "market": result.market,
        "latest_price": result.latest_price,
        "latest_date": result.latest_date,
        "trend": result.trend,
        "position": result.position,
        "risk_summary": result.risk_summary,
        "risk_verdict": result.risk_verdict,
        "signals": [
            {
                "date": s.date,
                "type": s.signal_type.value,
                "name": s.name,
                "description": s.description,
                "price": s.price,
                "confidence": s.confidence,
                "risk_level": s.risk_level.value if s.risk_level else None,
                "metadata": s.metadata,
            }
            for s in signals
        ],
        "generated_at": datetime.now().isoformat(),
    }

    return json.dumps(data, ensure_ascii=False, indent=2)
