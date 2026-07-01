#!/usr/bin/env python3
"""用 TradingAgents + DeepSeek 分析3只A股持仓"""

import os, sys, json
from datetime import date

# 配置 DeepSeek
os.environ["DEEPSEEK_API_KEY"] = "sk-46a8e76003994184a52fefa2892e1731"

# TradingAgents 项目路径
TA_PATH = "e:/work/stock/project/TradingAgents-astock"
sys.path.insert(0, TA_PATH)

from tradingagents.graph.trading_graph import TradingAgentsGraph

# DeepSeek 模型配置
CONFIG = {
    "llm_provider": "deepseek",
    "deep_think_llm": "deepseek-chat",
    "quick_think_llm": "deepseek-chat",
    "backend_url": "https://api.deepseek.com",
    "output_language": "Chinese",
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "project_dir": TA_PATH,
    "results_dir": f"{TA_PATH}/results",
    "data_cache_dir": f"{TA_PATH}/cache",
    "memory_log_path": f"{TA_PATH}/memory/trading_memory.md",
    "data_vendors": {
        "core_stock_apis": "a_stock",
        "technical_indicators": "a_stock",
        "fundamental_data": "a_stock",
        "news_data": "a_stock",
        "signal_data": "a_stock",
    },
}

STOCKS = [
    ("603799", "华友钴业"),
    ("688981", "中芯国际"),
    ("300373", "扬杰科技"),
]

today = date.today().strftime("%Y-%m-%d")
output_dir = f"e:/work/stock/daily_task/tradingagents_reports"
os.makedirs(output_dir, exist_ok=True)

for code, name in STOCKS:
    print(f"\n{'='*70}")
    print(f"  TradingAgents 分析: {name} ({code}) | {today}")
    print(f"{'='*70}")

    try:
        ta = TradingAgentsGraph(config=CONFIG)
        final_state, decision = ta.propagate(code, today)

        # 保存完整报告
        report_path = f"{output_dir}/{code}_{name}_{today}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump({
                "code": code, "name": name, "date": today,
                "decision": str(decision),
                "final_state": str(final_state)[:5000]
            }, f, ensure_ascii=False, indent=2, default=str)

        print(f"\n  决策: {decision}")
        print(f"  报告已保存: {report_path}")

    except Exception as e:
        print(f"  [FAIL] {e}")

print(f"\n全部完成，报告目录: {output_dir}")
