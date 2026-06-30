# Mystrategy — 统一量化投资框架

将 `E:\work\stock\` 下 **5 个项目 + 2 个数据源** 的代码去重、分层、统一为一个可复用的框架。

## 架构

```
mystrategy/
├── data/          Layer 1: 统一数据层 (9 vendors, 3 markets, router + cache)
├── factors/       Layer 2: 因子库 (60+ 因子, 8 大类)
├── signals/       Layer 3: 信号生成 (量价/K线形态/背离/突破)
├── strategies/    Layer 4: 策略引擎 (7 strategies, registry)
├── backtest/      Layer 5: 回测引擎 (事件驱动, T+1/涨跌停/手续费)
├── portfolio/     Layer 6: 组合管理 (优化/风控/再平衡)
├── research/      Layer 7: 投研框架 (Buffett清单/质量筛选/thesis跟踪)
├── agents/        Layer 8: AI多智能体 (placeholder)
├── kol/           Layer 9: KOL情绪 (placeholder)
├── cli/           Layer 10: 统一CLI
└── skills/        18 个 Claude Code 技能 (from ai-berkshire)
```

## 快速开始

```bash
# 安装
cd mystrategy
pip install -e ".[data]"      # 仅数据层
pip install -e ".[all]"       # 全部

# 数据
mystrategy data quote 600519
mystrategy data kline 000858 -d 500

# 因子
mystrategy factor 600519

# 信号
mystrategy signal scan 600519

# 策略
mystrategy strategy list
mystrategy strategy run 600519 rsi_macd -d 250

# 回测
mystrategy backtest 600519 triple_ma_trend -d 500

# 投研
mystrategy research checklist 贵州茅台
```

## 数据覆盖

| 市场 | 数据源 | 端点 | 特有功能 |
|------|--------|------|----------|
| A股 (沪深北) | mootdx/Tencent/Sina/Eastmoney/THS/Cninfo/Baostock | 40+ | 龙虎榜/打板/融资融券/北向/互动易 |
| 美股 | Yahoo/SEC EDGAR/Sina/Eastmoney | 18+ | SEC Filing/XBRL/期权链 |
| 港股 | Yahoo/Tencent/Sina/Eastmoney | 12+ | 实时行情/K线/资金流 |

## 合并来源

| 模块 | 来源 |
|------|------|
| `data/vendor/` | TradingAgents `a_stock.py` + stock-analyzer `a_stock.py` + astock-peg `datafeeds.py` |
| `data/markets/` | data-sources a-stock-data + global-stock-data SKILL.md 端点 |
| `factors/` | stock-analyzer `factors/` + ai-berkshire 18 skills 阈值 |
| `signals/` | volume-price-detector + stock-analyzer `strategies/volume_price.py` |
| `strategies/` | stock-analyzer `strategies/` 17策略 |
| `research/` | ai-berkshire skills → Python code |
| `skills/` | ai-berkshire `skills/*.md` (直接复制) |

## License

Apache 2.0 — 与原项目保持一致
