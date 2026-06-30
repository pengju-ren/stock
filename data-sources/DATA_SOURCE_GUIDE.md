# 数据源功能对照表

> 按四大场景分类：行情 → 研报 → 基础数据 → 公告
> 更新时间：2026-06-29

---

## 一、行情 (Market Data)

| 层级 | 工具 | 核心函数 | 说明 |
|------|------|---------|------|
| **首选** | `akshare` | `stock_zh_a_hist()` / `stock_hk_hist()` / `stock_us_hist()` | A/港/美 全市场历史K线 |
| | | `stock_zh_a_spot_em()` / `stock_hk_spot_em()` | 实时行情快照 |
| | | `stock_zh_index_daily()` / `bond_zh_hs_daily()` | 指数 / 可转债行情 |
| | | `fund_etf_spot_em()` | ETF 实时行情 |
| | | `stock_board_industry_index_ths()` | 同花顺行业板块指数 |
| **实时增强** | `easyquotation` | `use('tencent').get_realtime_quotes()` | 腾讯财经实时行情（秒级） |
| | | `use('tencent').market_snapshot()` | 全市场快照 |
| **离线/通达信** | `mootdx` | `Reader.factory().daily()` | 离线读取通达信本地日线 |
| | | `Quotes.factory().quotes()` | 通达信实时行情 |
| **容灾双核** | `Ashare` | `get_price(code, frequency, count)` | 新浪+腾讯双源，自动故障切换 |
| **分钟线** | `akshare` | `stock_zh_a_minute()` | A股分钟线 |

### 典型调用

```python
# A股历史日线
df = ak.stock_zh_a_hist(symbol='000001', period='daily', start_date='20250101', end_date='20250629', adjust='qfq')

# 港股历史日线
df = ak.stock_hk_hist(symbol='00700', period='daily', start_date='20250101', end_date='20250629', adjust='qfq')

# 腾讯财经实时行情
from easyquotation import use
q = use('tencent')
data = q.get_realtime_quotes(['sh600519', 'hk00700'])
```

---

## 二、研报 (Research Reports)

| 层级 | 工具 | 核心函数 | 说明 |
|------|------|---------|------|
| **首选** | `akshare` | `stock_research_report_em()` | 东方财富个股研报（含评级、目标价、三年EPS预测） |
| | | `stock_research_report_em(symbol='行业')` | 行业研报 |
| **机构持仓** | `akshare` | `stock_report_fund_hold()` | 基金持仓报告 |
| | | `stock_report_fund_hold_detail()` | 基金持仓明细 |
| **财报期** | `akshare` | `stock_report_disclosure()` | 财报预约披露时间表 |
| **港股研报** | `akshare` | `stock_financial_hk_report_em()` | 东财港股财报数据 |
| **美股研报** | `akshare` | `stock_financial_us_report_em()` | 东财美股财报数据 |
| **AI选股** | `pywencai` | `pywencai.get(query='券商研报 买入评级')` | 用自然语言筛选被研报覆盖的标的 |

### 典型调用

```python
# 获取贵州茅台的所有研报
df = ak.stock_research_report_em(symbol='600519')

# 基金持仓报告
df = ak.stock_report_fund_hold(symbol='600519')

# AI选股：筛选近期被调高评级的股票
import pywencai
df = pywencai.get(query='近30日券商调高评级，市盈率<30')
```

---

## 三、基础数据 (Fundamental Data)

| 子类 | 工具 | 核心函数 | 说明 |
|------|------|---------|------|
| **财务三表** | `akshare` | `stock_profit_sheet_by_report_em()` | 利润表（含同比环比） |
| | | `stock_balance_sheet_by_report_em()` | 资产负债表 |
| | | `stock_cash_flow_sheet_by_report_em()` | 现金流量表 |
| **财务指标** | `akshare` | `stock_financial_abstract_ths()` | 同花顺财务摘要（ROE/ROA/毛利率/净利率等） |
| | | `stock_financial_analysis_indicator()` | 财务分析指标 |
| **估值数据** | `akshare` | `stock_zh_a_spot_em()` → PE/PB/PS/市值 | A股估值快照 |
| | | `stock_hk_financial_indicator_em()` | 港股估值指标（EPS/BVPS/ROE/PE/PB） |
| **股东/股本** | `akshare` | `stock_zh_a_gdhs()` / `stock_zh_a_shares()` | 股东户数 / 股本结构 |
| | | `stock_shareholder_em()` | 十大股东 / 十大流通股东 |
| **行业/板块** | `akshare` | `stock_board_industry_name_ths()` | 同花顺行业分类 |
| | | `stock_board_concept_name_ths()` | 同花顺概念板块 |
| **IPO/新股** | `akshare` | `stock_zh_a_new_em()` / `stock_ipo_info()` | 新股发行 / IPO信息 |
| **宏观数据** | `akshare` | `macro_china_*()` 系列 | GDP/CPI/PMI/M2/社融... |

### 典型调用

```python
# 利润表
df = ak.stock_profit_sheet_by_report_em(symbol='600519')

# 同花顺财务摘要
df = ak.stock_financial_abstract_ths(symbol='600519', indicator='按报告期')

# 港股估值快照
df = ak.stock_hk_financial_indicator_em(symbol='00700')

# 十大股东
df = ak.stock_shareholder_em(symbol='600519', date='2025-12-31')
```

---

## 四、公告 (Announcements)

| 层级 | 工具 | 核心函数 | 说明 |
|------|------|---------|------|
| **首选** | `akshare` | `stock_notice_report()` | 巨潮资讯个股公告（最全） |
| | | `stock_individual_notice_report()` | 个股公告详情 |
| **科创板** | `akshare` | `stock_zh_kcb_report_em()` | 科创板公告/财报 |
| **财报预约** | `akshare` | `stock_report_disclosure()` | 财报披露预约时间表 |
| **新增持/减持** | `akshare` | `stock_zh_a_gdhs_detail_em()` | 股东增减持明细 |
| **回购** | `akshare` | `stock_share_buyback_em()` | 股票回购公告 |
| **股权质押** | `akshare` | `stock_gpzy_pledge_ratio_em()` | 股权质押比例 |
| **分红送转** | `akshare` | `stock_history_dividend()` | 分红送转历史 |
| **停复牌** | `akshare` | `stock_tfp_em()` | 停复牌信息 |
| **龙虎榜** | `akshare` | `stock_lhb_detail_em()` | 龙虎榜详情 |

### 典型调用

```python
# 获取贵州茅台全部公告
df = ak.stock_notice_report(symbol='600519')

# 股东增减持
df = ak.stock_zh_a_gdhs_detail_em(symbol='600519')

# 回购公告
df = ak.stock_share_buyback_em(symbol='600519')

# 分红送转历史
df = ak.stock_history_dividend(symbol='600519')
```

---

## 快速决策树

```
需要什么数据？
│
├─ 行情
│   ├─ 历史K线 → akshare.stock_zh_a_hist() / stock_hk_hist()
│   ├─ 实时行情 → easyquotation.use('tencent')
│   ├─ 分钟线   → akshare.stock_zh_a_minute()
│   └─ 通达信本地数据 → mootdx.Reader.factory()
│
├─ 研报
│   ├─ 个股研报+评级 → akshare.stock_research_report_em()
│   ├─ 机构持仓     → akshare.stock_report_fund_hold()
│   └─ AI智能筛选   → pywencai.get(query='...')
│
├─ 基础数据
│   ├─ 财务三表     → akshare.stock_profit_sheet_by_report_em() 等
│   ├─ 财务指标     → akshare.stock_financial_abstract_ths()
│   ├─ 估值快照     → akshare.stock_hk_financial_indicator_em()
│   ├─ 十大股东     → akshare.stock_shareholder_em()
│   └─ 宏观经济     → akshare.macro_china_*()
│
└─ 公告
    ├─ 全部公告     → akshare.stock_notice_report()
    ├─ 增减持       → akshare.stock_zh_a_gdhs_detail_em()
    ├─ 回购+分红    → akshare.stock_share_buyback_em() / stock_history_dividend()
    └─ 龙虎榜       → akshare.stock_lhb_detail_em()
```

---

## 数据源依赖汇总

| 源 | 包 | 优势场景 |
|----|-----|---------|
| **akshare** | `akshare` | 全覆盖——行情/研报/财务/公告，A/港/美 |
| **easyquotation** | `easyquotation` | 腾讯财经秒级实时行情 |
| **mootdx** | `mootdx` | 通达信本地离线数据 + 实时行情 |
| **pywencai** | `pywencai` | 同花顺问财 AI 自然语言选股 |
| **Ashare** | `Ashare.py` | 新浪+腾讯双核容灾行情 |
