# Volume Price Detector — 量价关系检测器

## 项目定位

基于「背个竹筐」《一站式详解量价关系》第5集教学体系的 CLI 工具。
核心功能：通过量价关系识别 5 种**卖出信号**。

## 环境

```bash
cd e:/work/stock/project/volume-price-detector

# 使用 stock-analyzer 的虚拟环境（共享依赖）
../stock-analyzer/.venv/Scripts/python -m volume_price_detector --help

# 或者创建独立环境
python -m venv .venv
. .venv/Scripts/activate
pip install -e .
```

## 命令体系

| 命令 | 用途 | 示例 |
|------|------|------|
| `scan <代码>` | 扫描单只股票的量价信号 | `python -m volume_price_detector scan 600519` |
| `batch` | 批量扫描整个市场 | `python -m volume_price_detector batch --market A --top 20` |
| `watchlist` | 扫描自选股列表 | `python -m volume_price_detector watchlist -f my_stocks.txt` |

### 选项

| 参数 | 说明 |
|------|------|
| `--days N` | 只显示最近 N 天的信号 |
| `--format terminal\|markdown\|json` | 输出格式 |
| `--file <路径>` | 指定自定义数据文件（CSV/Excel） |
| `--data-dir <路径>` | 指定 stock-analyzer cache 目录 |

## 五卖点信号（第5集核心内容）

| # | 信号 | 视频原文 | 风险 |
|---|------|----------|------|
| 1 | **放量滞涨** | "价格高位但涨不动，成交量突然放大，说明卖的人更多，是典型的出货位" | HIGH |
| 2 | **缩量新高** | "股价创新高但成交量缩小，说明上涨动能减弱，可能是量价背离" | HIGH |
| 3 | **高位长上影** | "高位长上影线，说明冲高失败，资金卖的坚决，卖点信号强" | HIGH |
| 4 | **放量大阴线** | "放量大阴线，说明资金态度转变，接盘无力，需警惕" | CRITICAL |
| 5 | **反弹缩量** | "反弹缩量，说明抛压小但买盘不积极，可能是技术性喘口气" | MEDIUM |

## 信号实现细节

| 信号 | 检测条件 |
|------|----------|
| 放量滞涨 | 高位(分位数>70%) + 量比>1.5 + 价格横盘(涨跌幅<0.5%) |
| 缩量新高 | 高位 + 创N日新高 + 当前量<前峰量×70% |
| 高位长上影 | 高位 + 上影线>实体×2 + 冲高回落>50%振幅 + 量比>0.8 |
| 放量大阴线 | 高位 + 量比>1.5 + 跌幅>3% + 实体>振幅×50% |
| 反弹缩量 | 下跌趋势 + 反弹上涨 + 反弹量<前段均量×70% + 反弹幅度<前期跌幅×50% |

## 数据来源

默认读取同级 `stock-analyzer` 项目的缓存数据：
- A 股: `../stock-analyzer/data/cache/a_kline_500d_v2.csv`
- ETF: `../stock-analyzer/data/cache/etf_kline_v1.csv`
- 港股: `../stock-analyzer/data/cache/hstech_kline_v1.csv`

也可通过 `--file` 指定自定义 CSV 文件（需含 OHLCV 列）。

## 注意事项

- 信号基于技术分析，需结合基本面判断
- 量价关系在 A 股有效性较高（散户市场特征明显）
- 多信号共振时可靠性更高，CRITICAL + HIGH 同时出现应高度重视
- 投资有风险，本工具仅供辅助参考
