"""CLI 入口 — argparse 命令解析。

用法:
    python -m volume_price_detector scan 600519
    python -m volume_price_detector batch --market A --top 20
    python -m volume_price_detector watchlist -f stocks.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Fix Windows GBK encoding issues with emoji/Unicode
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from volume_price_detector import __version__
from volume_price_detector.data import get_data_summary, get_stock_list, load_kline, load_from_file
from volume_price_detector.engine import scan_stock
from volume_price_detector.reporter import (
    print_batch_summary,
    print_result,
    to_json,
    to_markdown,
)


def cmd_scan(args: argparse.Namespace) -> None:
    """扫描单只股票。"""
    code = args.code.strip()

    try:
        if args.file:
            df = load_from_file(args.file)
            # 过滤指定代码
            df = df[df["code"].astype(str).str.replace(r"\.0$", "", regex=True) == code]
            if df.empty:
                print(f"错误: 文件中未找到代码 {code}")
                sys.exit(1)
        else:
            df = load_kline(
                codes=code,
                market=args.market,
                cache_dir=args.data_dir or None,
                days=args.days or None,
            )

        if df.empty:
            print(f"错误: 未找到 {code} 的数据。请先运行 stock-analyzer data fetch-a")
            sys.exit(1)

        # 获取名称
        name = ""
        stocks = get_stock_list(args.market, args.data_dir or None)
        for s in stocks:
            if s["code"] == code:
                name = s.get("name", "")
                break

        result = scan_stock(df, name=name, market=args.market)

        if args.format == "json":
            print(to_json(result, days=args.recent_days or None))
        elif args.format == "markdown":
            print(to_markdown(result, days=args.recent_days or None))
        else:
            print_result(
                result,
                days=args.recent_days or None,
                sell_only=args.sell_only,
                buy_only=args.buy_only,
            )

    except FileNotFoundError as e:
        print(f"数据错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"扫描失败: {e}")
        sys.exit(1)


def cmd_batch(args: argparse.Namespace) -> None:
    """批量扫描市场。"""
    try:
        stocks = get_stock_list(args.market, args.data_dir or None)
        if not stocks:
            print(f"错误: {args.market} 市场无可用股票数据")
            sys.exit(1)

        # 如果指定了 top N，只扫前 N 只（按成交额排序）
        if args.top:
            # 尝试按成交额排序选 Top N
            df_all = load_kline(
                market=args.market,
                cache_dir=args.data_dir or None,
                days=args.days or 60,
            )
            if not df_all.empty:
                # 按最近日期的成交额排序
                latest = df_all.groupby("code").apply(
                    lambda g: g.iloc[-1]["volume"] * g.iloc[-1]["close"]
                    if "amount" not in g.columns else g.iloc[-1]["amount"]
                    if "amount" in g.columns and not g["amount"].isna().all()
                    else g.iloc[-1]["volume"] * g.iloc[-1]["close"]
                ).sort_values(ascending=False)
                top_codes = latest.head(args.top).index.tolist()
            else:
                top_codes = [s["code"] for s in stocks[:args.top]]
        else:
            top_codes = [s["code"] for s in stocks]

        print(f"正在扫描 {args.market} 市场 {len(top_codes)} 只股票...\n")

        results = []
        scanned = 0
        for code in top_codes:
            try:
                df = load_kline(
                    codes=[code],
                    market=args.market,
                    cache_dir=args.data_dir or None,
                    days=args.days or None,
                )
                if df.empty:
                    continue

                name = ""
                for s in stocks:
                    if s["code"] == code:
                        name = s.get("name", "")
                        break

                result = scan_stock(df, name=name, market=args.market)
                results.append(result)

                if result.signals:
                    sell_count = len(result.sell_signals)
                    buy_count = len(result.buy_signals)
                    if sell_count > 0 or buy_count > 0:
                        print(f"  [{scanned+1}/{len(top_codes)}] {code} {name} "
                              f"— {sell_count}卖点 {buy_count}买点")

                scanned += 1
                if scanned % 50 == 0:
                    print(f"  ... {scanned}/{len(top_codes)} 已扫描")

            except Exception:
                continue

        # 输出汇总
        if args.format == "json":
            import json
            data = {
                "total": len(results),
                "with_signals": len([r for r in results if r.signals]),
                "results": [
                    {
                        "code": r.code,
                        "name": r.name,
                        "latest_price": r.latest_price,
                        "sell_count": len(r.sell_signals),
                        "buy_count": len(r.buy_signals),
                        "risk_summary": r.risk_summary,
                    }
                    for r in results if r.signals
                ],
            }
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print_batch_summary(results, top_n=args.top or 20)

    except FileNotFoundError as e:
        print(f"数据错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"批量扫描失败: {e}")
        sys.exit(1)


def cmd_watchlist(args: argparse.Namespace) -> None:
    """扫描自选股文件。"""
    watchlist_path = Path(args.file)
    if not watchlist_path.exists():
        print(f"错误: 文件不存在: {watchlist_path}")
        sys.exit(1)

    # 读取自选股列表（每行一个代码，或 CSV 格式）
    codes = []
    suffix = watchlist_path.suffix.lower()
    if suffix == ".csv":
        import pandas as pd
        df = pd.read_csv(str(watchlist_path), dtype={"code": str})
        codes = df["code"].astype(str).str.replace(r"\.0$", "", regex=True).tolist()
    elif suffix == ".txt":
        with open(watchlist_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    codes.append(line.split()[0] if line.split() else line)
    else:
        print(f"不支持的文件格式: {suffix}。支持 .csv / .txt")
        sys.exit(1)

    if not codes:
        print("自选股列表为空")
        sys.exit(1)

    print(f"扫描 {len(codes)} 只自选股...\n")

    results = []
    for code in codes:
        try:
            df = load_kline(
                codes=[code],
                market=args.market,
                cache_dir=args.data_dir or None,
                days=args.days or None,
            )
            if df.empty:
                print(f"  [{code}] 无数据，跳过")
                continue

            result = scan_stock(df, market=args.market)
            results.append(result)

            if args.format == "json":
                print(to_json(result, days=args.recent_days or None))
            elif args.format == "markdown":
                print(to_markdown(result, days=args.recent_days or None))
            else:
                print_result(
                    result,
                    days=args.recent_days or None,
                    sell_only=args.sell_only,
                    buy_only=args.buy_only,
                )

        except Exception as e:
            print(f"  [{code}] 扫描失败: {e}")

    # 汇总
    if not results:
        return

    with_sell = sum(1 for r in results if r.sell_signals)
    with_buy = sum(1 for r in results if r.buy_signals)
    print(f"\n📊 汇总: {len(results)} 只, "
          f"有卖点: {with_sell} 只, 有买点: {with_buy} 只")


def cmd_info(args: argparse.Namespace) -> None:
    """显示数据概览。"""
    summary = get_data_summary(args.data_dir or None)
    print(f"\n📊 数据概览\n")
    for market, info in summary.items():
        if info["stocks"] > 0:
            print(f"  {market}股: {info['stocks']} 只, "
                  f"{info['bars']:,} 条K线, "
                  f"{info['date_from']} ~ {info['date_to']}")
        else:
            print(f"  {market}股: 数据不可用")
    print()


def main() -> None:
    """CLI 主入口。"""
    parser = argparse.ArgumentParser(
        prog="volume-price-detector",
        description="量价关系检测器 — 基于「背个竹筐」教学体系的买卖信号识别工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m volume_price_detector scan 600519           # 扫描贵州茅台
  python -m volume_price_detector scan 600519 --sell-only  # 只看卖点
  python -m volume_price_detector batch --market A --top 20 # A股Top20
  python -m volume_price_detector watchlist -f my_stocks.txt # 自选股
  python -m volume_price_detector info                   # 数据概览
        """,
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # ── scan ──
    scan_parser = subparsers.add_parser("scan", help="扫描单只股票")
    scan_parser.add_argument("code", help="股票代码 (如 600519)")
    scan_parser.add_argument("--market", "-m", default="A", choices=["A", "ETF", "HK"],
                             help="市场 (默认: A)")
    scan_parser.add_argument("--file", "-f", help="从自定义 CSV/Excel 文件读取数据")
    scan_parser.add_argument("--data-dir", help="stock-analyzer cache 目录路径")
    scan_parser.add_argument("--days", type=int, help="只加载最近 N 天数据")
    scan_parser.add_argument("--recent-days", type=int, default=20,
                             help="只显示最近 N 天的信号 (默认: 20)")
    scan_parser.add_argument("--sell-only", action="store_true", help="只显示卖出信号")
    scan_parser.add_argument("--buy-only", action="store_true", help="只显示买入信号")
    scan_parser.add_argument("--format", choices=["terminal", "markdown", "json"],
                             default="terminal", help="输出格式 (默认: terminal)")
    scan_parser.set_defaults(func=cmd_scan)

    # ── batch ──
    batch_parser = subparsers.add_parser("batch", help="批量扫描市场")
    batch_parser.add_argument("--market", "-m", default="A", choices=["A", "ETF", "HK"],
                              help="市场 (默认: A)")
    batch_parser.add_argument("--top", "-n", type=int, help="只扫描成交额 Top N 只")
    batch_parser.add_argument("--data-dir", help="stock-analyzer cache 目录路径")
    batch_parser.add_argument("--days", type=int, help="只加载最近 N 天数据")
    batch_parser.add_argument("--format", choices=["terminal", "json"],
                              default="terminal", help="输出格式")
    batch_parser.set_defaults(func=cmd_batch)

    # ── watchlist ──
    wl_parser = subparsers.add_parser("watchlist", help="扫描自选股文件")
    wl_parser.add_argument("--file", "-f", required=True, help="自选股文件路径 (.txt 或 .csv)")
    wl_parser.add_argument("--market", "-m", default="A", choices=["A", "ETF", "HK"])
    wl_parser.add_argument("--data-dir", help="stock-analyzer cache 目录路径")
    wl_parser.add_argument("--days", type=int, help="只加载最近 N 天数据")
    wl_parser.add_argument("--recent-days", type=int, default=20, help="只显示最近 N 天的信号")
    wl_parser.add_argument("--sell-only", action="store_true", help="只显示卖出信号")
    wl_parser.add_argument("--buy-only", action="store_true", help="只显示买入信号")
    wl_parser.add_argument("--format", choices=["terminal", "markdown", "json"],
                           default="terminal", help="输出格式")
    wl_parser.set_defaults(func=cmd_watchlist)

    # ── info ──
    info_parser = subparsers.add_parser("info", help="显示数据概览")
    info_parser.add_argument("--data-dir", help="stock-analyzer cache 目录路径")
    info_parser.set_defaults(func=cmd_info)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
