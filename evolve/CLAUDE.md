# Stock Evolution Engine — 策略自我进化系统

## 定位

这不是选股系统，这是**改进选股系统的系统**。

每一轮 Loop 做五件事：
1. **找到系统的弱点** — 哪个策略不行了？哪个因子失效了？市场风格变了吗？
2. **动手改进** — 修策略、调权重、加新逻辑、集成外部优秀思路
3. **严格验证** — 回测+滚动验证+压力测试+过拟合检测
4. **合入系统** — 通过验证的新策略写入 evolve/strategies/
5. **再来一轮** — 永不停止，系统持续变强

## 目录结构

```
evolve/
├── alpha/                    # 进化引擎核心
│   ├── orchestrator.py       # 主循环控制器
│   ├── config.py             # 进化参数配置
│   ├── state.py              # 循环状态管理
│   ├── auditor.py            # 策略绩效审计
│   ├── factor_doctor.py      # 因子健康检测
│   ├── gap_scanner.py        # 知识缺口扫描
│   ├── inspiration_scanner.py # 外部灵感扫描
│   ├── regime_monitor.py     # 市场状态变化检测
│   ├── ledger_analyzer.py    # 预测账本分析
│   ├── builder.py            # 策略构建/修复
│   ├── verifier.py           # 回测验证引擎
│   ├── shipper.py            # 合入系统
│   └── knowledge_base.py     # 100本经典投资书籍知识库
├── strategies/               # 进化产出：改进后的策略代码
├── experiments/              # 失败尝试归档
├── changelogs/               # 每次改进的变更记录
├── reports/                  # 体检报告、周报
├── knowledge/                # 结构化知识库
│   ├── books/                # 100本书摘要
│   └── frameworks/           # 投资框架库
├── prediction_ledger.json    # 预测追踪账本
└── state.json                # 进化状态
```

## 使用方式

```bash
# 启动一轮进化
cd e:/work/stock/evolve
python -m alpha.orchestrator

# 只跑策略体检
python -m alpha.auditor

# 只扫描外部灵感
python -m alpha.inspiration_scanner

# 查看进化历史
cat changelogs/*.md
```

## 设计原则

1. **不修改现有代码** — 所有产出在 evolve/ 下，参考现有项目但不触碰
2. **量化驱动** — 所有决策基于回测数据，不凭感觉
3. **对抗验证** — 每个改进必须通过压力测试和过拟合检测
4. **知识沉淀** — 失败的尝试也要归档，避免重复犯错
5. **永不停止** — 只要有新的数据、论文、书籍、大V观点，就继续进化

## 参考项目（只读）

- `../project/stock-analyzer/` — 当前最强的分析系统
- `../mystrategy/` — 统一量化框架
- `../reference_code/qlib/` — 微软AI量化平台
- `../project/TradingAgents-astock/` — 多代理交易系统
- `../project/volume-price-detector/` — 量价检测
