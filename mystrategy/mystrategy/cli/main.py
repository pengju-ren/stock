"""Unified CLI for mystrategy.

Usage:
    mystrategy data quote 600519          # Get real-time quote
    mystrategy data kline 600519 -d 250   # Get K-line data
    mystrategy factor 600519               # Compute all factors
    mystrategy signal scan 600519          # Scan for trading signals
    mystrategy strategy list               # List available strategies
    mystrategy strategy run 600519 rsi_macd  # Run strategy
    mystrategy backtest 600519 rsi_macd    # Run backtest
    mystrategy research checklist 600519   # Run Buffett checklist
    mystrategy research quality 600519     # Run quality screen
    mystrategy web                         # Launch web UI (Streamlit)
"""

from __future__ import annotations

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="mystrategy",
        description="统一量化投资框架",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # ── data ──
    data_parser = subparsers.add_parser("data", help="数据获取")
    data_sub = data_parser.add_subparsers(dest="data_cmd")

    quote_p = data_sub.add_parser("quote", help="实时行情")
    quote_p.add_argument("code", help="股票代码")
    quote_p.add_argument("-m", "--market", default="a_stock", choices=["a_stock", "us_stock", "hk_stock"])

    kline_p = data_sub.add_parser("kline", help="K线数据")
    kline_p.add_argument("code")
    kline_p.add_argument("-d", "--days", type=int, default=250)
    kline_p.add_argument("-m", "--market", default="a_stock")

    news_p = data_sub.add_parser("news", help="新闻")
    news_p.add_argument("code")
    news_p.add_argument("-n", "--count", type=int, default=15)

    # ── factor ──
    factor_parser = subparsers.add_parser("factor", help="因子计算")
    factor_parser.add_argument("code")
    factor_parser.add_argument("-m", "--market", default="a_stock")
    factor_parser.add_argument("--factor", default="all", help="Factor name or 'all'")

    # ── signal ──
    signal_parser = subparsers.add_parser("signal", help="信号检测")
    signal_sub = signal_parser.add_subparsers(dest="signal_cmd")

    scan_p = signal_sub.add_parser("scan", help="扫描量价信号")
    scan_p.add_argument("code")
    scan_p.add_argument("-d", "--days", type=int, default=500)

    # ── strategy ──
    strategy_parser = subparsers.add_parser("strategy", help="策略引擎")
    strategy_sub = strategy_parser.add_subparsers(dest="strategy_cmd")

    strat_list = strategy_sub.add_parser("list", help="列出所有策略")

    strat_run = strategy_sub.add_parser("run", help="运行策略")
    strat_run.add_argument("code")
    strat_run.add_argument("strategy", help="Strategy name")
    strat_run.add_argument("-d", "--days", type=int, default=250)

    # ── backtest ──
    bt_parser = subparsers.add_parser("backtest", help="回测")
    bt_parser.add_argument("code")
    bt_parser.add_argument("strategy")
    bt_parser.add_argument("-d", "--days", type=int, default=500)
    bt_parser.add_argument("--capital", type=float, default=1_000_000)

    # ── research ──
    research_parser = subparsers.add_parser("research", help="投研框架")
    research_sub = research_parser.add_subparsers(dest="research_cmd")

    check_p = research_sub.add_parser("checklist", help="Buffett预购清单")
    check_p.add_argument("company")

    quality_p = research_sub.add_parser("quality", help="7指标质量筛选")
    quality_p.add_argument("company")

    # ── web ──
    web_parser = subparsers.add_parser("web", help="启动Web UI")

    args = parser.parse_args()

    if args.command == "data":
        _handle_data(args)
    elif args.command == "factor":
        _handle_factor(args)
    elif args.command == "signal":
        _handle_signal(args)
    elif args.command == "strategy":
        _handle_strategy(args)
    elif args.command == "backtest":
        _handle_backtest(args)
    elif args.command == "research":
        _handle_research(args)
    elif args.command == "web":
        _handle_web(args)
    else:
        parser.print_help()


def _handle_data(args):
    from mystrategy.data import a_stock, us_stock, hk_stock

    market_map = {"a_stock": a_stock, "us_stock": us_stock, "hk_stock": hk_stock}
    api = market_map.get(args.market, a_stock)

    if args.data_cmd == "quote":
        result = api.quote(args.code) if args.market == "a_stock" else api.realtime([args.code])
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif args.data_cmd == "kline":
        if args.market == "a_stock":
            df = api.kline(args.code, count=args.days)
        elif args.market == "us_stock":
            df = api.kline(args.code, years=args.days // 250 + 1)
        else:
            df = api.kline(args.code, years=args.days // 250 + 1)
        print(f"Loaded {len(df)} bars")
        print(df.tail(10).to_string())

    elif args.data_cmd == "news":
        result = api.stock_news(args.code, args.count)
        for r in result:
            print(f"[{r.get('time', '')}] {r.get('title', '')}")


def _handle_factor(args):
    from mystrategy.data import a_stock
    from mystrategy.factors import FACTOR_REGISTRY

    df = a_stock.kline(args.code, count=250)
    if df.empty:
        print("No data")
        return

    quote = a_stock.quote(args.code)
    data = {"kline": df, "quote": quote}

    if args.factor == "all":
        from mystrategy.factors import compute_all
        results = compute_all(data)
        for name, scores in results.items():
            print(f"\n=== {name} ===")
            for k, v in scores.items():
                print(f"  {k}: {v:.3f}" if isinstance(v, float) else f"  {k}: {v}")
    else:
        cls = FACTOR_REGISTRY.get(args.factor)
        if cls:
            instance = cls()
            scores = instance.compute(data)
            for k, v in scores.items():
                print(f"  {k}: {v:.3f}" if isinstance(v, float) else f"  {k}: {v}")


def _handle_signal(args):
    from mystrategy.data import a_stock
    from mystrategy.signals import scan_stock

    df = a_stock.kline(args.code, count=args.days)
    if df.empty:
        print("No data")
        return

    result = scan_stock(df)
    print(f"\n{result.code} {result.name}")
    print(f"风险判定: {result.risk_verdict}")
    print(f"信号总数: {len(result.signals)}")

    for sig in result.signals:
        tag = "🟢" if sig.signal_type.value == "BUY" else "🔴"
        print(f"  {tag} [{sig.date}] {sig.name} @{sig.price:.2f} ({sig.risk_level.value})")
        print(f"     {sig.description}")


def _handle_strategy(args):
    from mystrategy.strategies import StrategyRegistry

    if args.strategy_cmd == "list":
        for name in StrategyRegistry.list_all():
            cls = StrategyRegistry.get(name)
            if cls:
                print(f"  {cls.name:20s} — {cls.description}")

    elif args.strategy_cmd == "run":
        from mystrategy.data import a_stock
        df = a_stock.kline(args.code, count=args.days)
        if df.empty:
            print("No data")
            return

        strategy = StrategyRegistry.create(args.strategy)
        if strategy is None:
            print(f"Unknown strategy: {args.strategy}")
            return

        trades = strategy.run({"kline": df})
        for t in trades:
            tag = "BUY" if t["action"] == "BUY" else "SELL"
            print(f"  [{tag}] @{t['price']:.2f} x{t['size']} — {t['reason'][:60]}")


def _handle_backtest(args):
    from mystrategy.data import a_stock
    from mystrategy.strategies import StrategyRegistry
    from mystrategy.backtest import run_backtest

    df = a_stock.kline(args.code, count=args.days)
    if df.empty:
        print("No data")
        return

    cls = StrategyRegistry.get(args.strategy)
    if cls is None:
        print(f"Unknown strategy: {args.strategy}")
        return

    result = run_backtest(cls, {"kline": df})

    print(f"\n{'='*50}")
    print(f"Backtest: {args.code} x {args.strategy}")
    print(f"{'='*50}")
    print(f"初始资金:   {result.initial_capital:,.0f}")
    print(f"最终价值:   {result.final_value:,.0f}")
    print(f"总收益率:   {result.total_return:.2f}%")
    print(f"年化收益:   {result.annual_return:.2f}%")
    print(f"最大回撤:   {result.max_drawdown:.2f}%")
    print(f"夏普比率:   {result.sharpe_ratio:.2f}")
    print(f"Calmar:     {result.calmar_ratio:.2f}")
    print(f"胜率:       {result.win_rate:.1f}%")
    print(f"交易次数:   {result.total_trades}")
    if result.metrics.get("alpha") is not None:
        print(f"Alpha:      {result.metrics['alpha']:.2f}%")


def _handle_research(args):
    if args.research_cmd == "checklist":
        from mystrategy.research import run_checklist
        result = run_checklist(args.company, {})
        print(f"\n{args.company} — Buffett预购清单")
        print(f"总分: {result.overall_score}/30")
        print(f"通过: {'YES' if result.passed else 'NO'}")
        if result.veto_triggered:
            print(f"否决: {result.veto_reason}")
        for g in result.gates:
            status = "✓" if g.passed else "✗"
            stars = "★" * g.score + "☆" * (5 - g.score)
            print(f"  [{status}] Gate {g.gate}: {g.name} {stars}")
            if g.notes:
                print(f"       {g.notes}")

    elif args.research_cmd == "quality":
        from mystrategy.research import run_quality_screen
        result = run_quality_screen(args.company, {})
        print(f"\n{args.company} — 质量筛选")
        print(f"通过: {result.passed_count}/{result.total_count}")
        print(f"判定: {result.verdict}")
        for ind in result.indicators:
            status = "✓" if ind["passed"] else "✗"
            exempt = " (豁免)" if ind.get("exempted") else ""
            print(f"  [{status}] {ind['name']}: {ind['value']} {ind['threshold']}{exempt}")


def _handle_web(args):
    print("Starting web UI...")
    try:
        import streamlit.web.cli as st_cli
        import os
        app_path = os.path.join(os.path.dirname(__file__), "..", "web", "app.py")
        sys.argv = ["streamlit", "run", app_path]
        st_cli.main()
    except ImportError:
        print("Streamlit not installed. pip install mystrategy[web]")


cli = main

if __name__ == "__main__":
    main()
