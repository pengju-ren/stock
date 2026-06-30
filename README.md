# Stock — 量化投资研究项目

个人股票研究与量化投资框架，覆盖 A股/港股/美股 多市场分析。

## 目录结构

```
stock/
├── mystrategy/                  # 统一量化投资框架（Python）
│   ├── data/                    # 多数据源接入（东方财富、新浪、腾讯、雅虎等）
│   ├── factors/                 # 因子库（基本面、技术面、估值、情绪、资金流）
│   ├── strategies/              # 策略库（趋势、动量、均值回归、量价）
│   ├── signals/                 # 信号引擎（K线形态、量价检测）
│   ├── backtest/                # 回测引擎
│   ├── research/                # 研究工具（清单、质量筛选、投资论文）
│   └── skills/                  # Claude Code Skills（18个投资研究技能）
├── project/
│   ├── claude-code-s5/          # 投资研究 5 步法（选赛道 → 拍板）
│   ├── volume-price-detector/   # 量价关系检测 CLI 工具
│   ├── TradingAgents-astock/    # TradingAgents A股版
│   ├── ai-berkshire/            # AI 版伯克希尔
│   ├── astock-peg/              # A股 PEG 分析
│   └── stock-analyzer/          # 股票分析器
├── data-sources/                # 数据源（A股、全球）
├── reference_code/              # 参考代码（qlib 等）
└── research_semiconductor_tech.py  # 半导体技术研究脚本
```

## 主要特性

- **多市场支持**：A股、港股、美股
- **多数据源**：baostock、东方财富、新浪、腾讯、雅虎财经、SEC EDGAR
- **丰富因子库**：估值、质量、技术、情绪、资金流、行业、宏观
- **策略框架**：可组合的策略 + 信号 + 回测体系
- **AI 驱动研究**：Claude Code S5 五步法，从赛道选择到最终决策

## 快速开始

```bash
# 安装 mystrategy
cd mystrategy
pip install -e .

# 运行量价检测
cd project/volume-price-detector
pip install -e .
volume-price-detect --symbol 000001
```

## 免责声明

本项目仅供学习和研究使用，不构成任何投资建议。投资有风险，入市需谨慎。
