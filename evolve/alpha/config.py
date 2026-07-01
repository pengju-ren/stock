"""
进化引擎配置 — 所有可调参数集中管理。

修改此文件即可调整进化行为的激进程度、验证标准、扫描频率等。
"""

import os

# ============================================================
# 路径配置
# ============================================================
EVOLVE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALPHA_DIR = os.path.join(EVOLVE_ROOT, "alpha")
STRATEGIES_DIR = os.path.join(EVOLVE_ROOT, "strategies")
EXPERIMENTS_DIR = os.path.join(EVOLVE_ROOT, "experiments")
CHANGELOGS_DIR = os.path.join(EVOLVE_ROOT, "changelogs")
REPORTS_DIR = os.path.join(EVOLVE_ROOT, "reports")
KNOWLEDGE_DIR = os.path.join(EVOLVE_ROOT, "knowledge")
STATE_FILE = os.path.join(EVOLVE_ROOT, "state.json")
LEDGER_FILE = os.path.join(EVOLVE_ROOT, "prediction_ledger.json")

# 现有项目路径（只读参考）
STOCK_ANALYZER_ROOT = os.path.join(os.path.dirname(EVOLVE_ROOT), "project", "stock-analyzer")
STOCK_ANALYZER_SRC = os.path.join(STOCK_ANALYZER_ROOT, "stock_analyzer")
MYSTRATEGY_ROOT = os.path.join(os.path.dirname(EVOLVE_ROOT), "mystrategy")
QLIB_ROOT = os.path.join(os.path.dirname(EVOLVE_ROOT), "reference_code", "qlib")

os.makedirs(STRATEGIES_DIR, exist_ok=True)
os.makedirs(EXPERIMENTS_DIR, exist_ok=True)
os.makedirs(CHANGELOGS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

# ============================================================
# 进化循环参数
# ============================================================

# 每轮进化最大尝试次数（同一弱点尝试改进的次数上限）
MAX_BUILD_ATTEMPTS = 3

# 每轮进化聚焦的弱点数量上限（一轮不会试图修所有问题）
MAX_WEAKNESSES_PER_CYCLE = 2

# 最小可接受改进幅度（改进必须带来至少这么多百分点的提升）
MIN_IMPROVEMENT_THRESHOLD = 0.05  # 5% 相对提升

# 自动触发条件
AUTO_TRIGGER_WEEKLY = True       # 每周自动跑一轮
AUTO_TRIGGER_DRAWDOWN = True    # 实盘回撤超阈值自动触发
AUTO_TRIGGER_DRAWDOWN_PCT = 0.15  # 15% 回撤触发紧急诊断
AUTO_TRIGGER_INSPIRATION = True  # 检测到高价值外部灵感触发

# ============================================================
# 验证标准（策略合入门槛）
# ============================================================

VERIFICATION = {
    "min_annual_return_vs_benchmark": 0.05,  # 年化至少超越基准 5%
    "min_sharpe_ratio": 0.8,                 # 最低夏普比率
    "max_drawdown": 0.25,                    # 最大回撤不超过 25%
    "min_win_rate": 0.40,                    # 最低胜率 40%
    "min_profit_factor": 1.3,                # 盈亏比至少 1.3
    "rolling_window_count": 6,               # 滚动回测窗口数
    "rolling_window_months": 6,              # 每个窗口 6 个月
    "rolling_positive_required": 4,          # 至少 4/6 窗口正收益
    "monte_carlo_runs": 1000,                # 蒙特卡洛模拟次数
    "monte_carlo_var95_ok": True,            # 95% VaR 检查
    "param_sensitivity_range": 0.10,         # 参数敏感性 ±10%
    "param_sensitivity_max_drop": 0.30,      # 参数微调后收益最多降 30%
    "max_correlation_with_existing": 0.70,   # 与现有策略最大相关性
}

# ============================================================
# 因子健康阈值
# ============================================================

FACTOR_HEALTH = {
    "min_ic_absolute": 0.02,       # IC 绝对值低于此值 → 失效
    "ic_decline_threshold": 0.03,  # IC 下降超过此值 → 衰减预警
    "ic_rolling_window": 60,       # 滚动 IC 计算窗口（交易日）
    "ic_significance_level": 0.05, # IC 显著性水平
    "max_correlation_between_factors": 0.80,  # 因子间共线性警告
}

# ============================================================
# 策略健康阈值
# ============================================================

STRATEGY_HEALTH = {
    "min_annual_return": 0.0,          # 年化收益低于此值 → 警告
    "max_drawdown_trigger": 0.25,      # 回撤超过此值 → 警告
    "min_sharpe_trigger": 0.3,         # 夏普低于此值 → 警告
    "max_consecutive_losing_months": 4, # 连续亏损月数
    "performance_lookback_months": 6,   # 绩效回溯月数
}

# ============================================================
# 外部灵感扫描配置
# ============================================================

INSPIRATION = {
    "github_search_queries": [
        "quantitative trading strategy python 2025",
        "A股 量化 选股 策略 GitHub",
        "multi-agent stock trading LLM",
        "machine learning stock prediction",
    ],
    "arxiv_categories": ["q-fin.PM", "q-fin.ST", "q-fin.TR"],
    "xueqiu_hot_keywords": ["策略", "选股", "因子", "回测", "轮动", "哑铃"],
    "max_articles_per_source": 20,
    "scan_interval_days": 7,
}

# ============================================================
# 知识库配置
# ============================================================

KNOWLEDGE = {
    "books_json": os.path.join(KNOWLEDGE_DIR, "books.json"),
    "frameworks_dir": os.path.join(KNOWLEDGE_DIR, "frameworks"),
    "total_books_target": 100,
    "book_categories": [
        "value_investing",
        "growth_investing",
        "technical_analysis",
        "quantitative_trading",
        "behavioral_finance",
        "financial_history",
        "accounting_forensics",
        "portfolio_management",
        "market_psychology",
        "macro_economics",
    ],
}

# ============================================================
# 市场状态监控
# ============================================================

REGIME = {
    "volatility_lookback": 60,       # 波动率计算窗口
    "correlation_lookback": 120,     # 个股相关性计算窗口
    "rotation_speed_window": 20,     # 板块轮动速度窗口
    "regime_change_threshold": 0.3,  # 状态变化检测阈值
}

# ============================================================
# 日志
# ============================================================
LOG_LEVEL = os.getenv("EVOLVE_LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
