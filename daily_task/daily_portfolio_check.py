#!/usr/bin/env python3
"""
每日持仓分析 V3 — 基于项目策略引擎的真量化分析

策略来源：
  - Alpha Composite (CAN SLIM + 双动量 + 趋势, 三票投票制)
  - 量价检测器 (5个卖出信号检测)
  - 双动量排名 (6月动量 + 3月动量加权)
  - 市场状态检测 (牛市/熊市/震荡/高波动)

数据源：腾讯行情(实时) + 新浪K线(60日) + 东财资金流
"""

import urllib.request, json, sys, io, os, time, random
from datetime import date, datetime

# UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
UA = "Mozilla/5.0"

# ═══════════════ 持仓 ═══════════════
HOLDINGS = [
    ("513120","港股通创新药ETF","ETF","sh","创新药"),
    ("512880","证券ETF","ETF","sh","金融"),
    ("159851","金融科技ETF","ETF","sz","金融"),
    ("159530","机器人ETF","ETF","sz","科技成长"),
    ("159870","化工ETF","ETF","sz","周期资源"),
    ("06855","亚盛医药-B","HK","hk","创新药"),
    ("00700","腾讯控股","HK","hk","互联网"),
    ("01772","赣锋锂业","HK","hk","周期资源"),
    ("513130","恒生科技ETF","ETF","sh","科技成长"),
    ("03690","美团-W","HK","hk","互联网"),
    ("09688","再鼎医药","HK","hk","创新药"),
    ("159876","有色ETF","ETF","sz","周期资源"),
    ("603799","华友钴业","A","sh","周期资源"),
    ("159981","能源化工ETF","ETF","sz","周期资源"),
    ("588000","科创50ETF","ETF","sh","科技成长"),
    ("688981","中芯国际","A","sh","科技成长"),
    ("510880","红利ETF","ETF","sh","防御"),
    ("515790","光伏ETF","ETF","sh","新能源"),
    ("159941","纳指ETF","ETF","sz","海外"),
    ("300373","扬杰科技","A","sz","科技成长"),
]

# ═══════════════ 数据获取 ═══════════════
def fetch_quotes():
    """腾讯实时行情"""
    a_codes = [(c,m) for c,_,t,_,_ in HOLDINGS if t in ("ETF","A") for c,m in [(c,"sh" if c[0] in "569" else "sz")]]
    # Actually use the market field from holdings
    prefixed_a = [f"{m}{c}" for c,_,_,m,_ in HOLDINGS if m in ("sh","sz")]
    prefixed_hk = [f"hk{c}" for c,_,t,_,_ in HOLDINGS if t=="HK"]

    result = {}

    # A股/ETF
    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed_a)
    req = urllib.request.Request(url); req.add_header("User-Agent", UA)
    resp = urllib.request.urlopen(req, timeout=10)
    for line in resp.read().decode("gbk").strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line: continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53: continue
        code = key[2:]
        result[code] = {
            "name": vals[1], "price": float(vals[3] or 0),
            "chg_pct": float(vals[32] or 0), "pe": float(vals[39] or 0),
            "pb": float(vals[46] or 0), "mcap": float(vals[44] or 0),
            "amount": float(vals[37] or 0), "turnover": float(vals[38] or 0),
            "vol_ratio": float(vals[49] or 0),
        }

    # 港股
    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed_hk)
    req = urllib.request.Request(url); req.add_header("User-Agent", UA)
    resp = urllib.request.urlopen(req, timeout=10)
    for line in resp.read().decode("gbk").strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line: continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 50: continue
        code = key[2:]
        result[code] = {
            "name": vals[1], "price": float(vals[3] or 0),
            "chg_pct": float(vals[32] or 0), "pe": float(vals[57] or 0),
            "pb": float(vals[58] or 0), "mcap": float(vals[44] or 0),
            "amount": float(vals[37] or 0), "turnover": 0, "vol_ratio": 0,
        }
    return result


def fetch_kline_sina(code, market, days=60):
    """新浪财经日K线"""
    prefix = {"sh":"sh","sz":"sz","bj":"bj"}.get(market, "sh")
    url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={prefix}{code}&scale=240&ma=no&datalen={days}"
    try:
        req = urllib.request.Request(url); req.add_header("User-Agent", UA)
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("gbk"))
        if not data: return None
        return [{"date":b["day"],"open":float(b["open"]),"high":float(b["high"]),
                 "low":float(b["low"]),"close":float(b["close"]),"volume":float(b["volume"])} for b in data]
    except Exception:
        return None


def fetch_fund_flow(code):
    """东财120日主力资金流"""
    secid = f"1.{code}" if code[0] in "56" else f"0.{code}"
    params = {"secid":secid,"klt":101,"fields1":"f1,f2,f3,f7","fields2":"f51,f52,f53,f54,f55,f56,f57","lmt":"60"}
    try:
        url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url); req.add_header("User-Agent", UA)
        req.add_header("Referer","https://quote.eastmoney.com/")
        d = json.loads(urllib.request.urlopen(req, timeout=10).read().decode("utf-8"))
        rows = []
        for line in d.get("data",{}).get("klines",[]):
            p = line.split(",")
            if len(p)>=6: rows.append({"date":p[0],"main_net":float(p[1])})
        return rows
    except Exception:
        return []


# ═══════════════ 策略核心逻辑 ═══════════════
# 以下逻辑直接来自 evolve/strategies/ 下的实际策略

def cs_score(klines):
    """CAN SLIM 打分 (0-7), 来自 can_slim.py"""
    if not klines or len(klines) < 63: return 0, []
    closes = [k["close"] for k in klines]
    vols = [k["volume"] for k in klines]
    price = closes[-1]
    score = 0; reasons = []

    # C: 63日涨幅 > 10%
    if len(closes) >= 63 and (price/closes[-63]-1)*100 > 10:
        score +=1; reasons.append("C:季度涨幅>10%")
    # A: 252日涨幅 > 15%
    if len(closes) >= 252 and (price/closes[-252]-1)*100 > 15:
        score +=1; reasons.append("A:年度涨幅>15%")
    # N: 接近20日新高
    if len(closes) >= 20 and price >= max(closes[-20:])*0.97:
        score +=1; reasons.append("N:接近20日新高")
    # S: 5日均量 > 20日均量*1.2
    if len(vols) >= 20 and sum(vols[-5:])/5 > sum(vols[-20:])/20*1.2:
        score +=1; reasons.append("S:放量")
    # L: 60日涨幅 > 10%
    if len(closes) >= 60 and (price/closes[-60]-1)*100 > 10:
        score +=1; reasons.append("L:60日领涨")
    # M: 价格 > MA60
    if len(closes) >= 60 and price > sum(closes[-60:])/60:
        score +=1; reasons.append("M:站上MA60")
    # I: 机构持仓 (跳过，无数据)
    return score, reasons


def dm_score(klines):
    """双动量打分, 来自 dual_momentum.py"""
    if not klines or len(klines) < 126: return 0, []
    closes = [k["close"] for k in klines]
    price = closes[-1]
    reasons = []

    # 绝对动量: 6个月回报
    mom6 = (price/closes[-126]-1)*100 if len(closes)>=126 else 0
    mom3 = (price/closes[-63]-1)*100 if len(closes)>=63 else 0

    # 综合得分 = 12月*0.6 + 3月*0.4
    composite = mom6*0.6 + mom3*0.4

    if composite > 10: reasons.append(f"双动量强劲({composite:.0f}%)")
    elif composite > 0: reasons.append(f"双动量温和({composite:.0f}%)")
    else: reasons.append(f"双动量转弱({composite:.0f}%)")

    # 映射到0-10范围
    score = max(0, min(10, composite/5 + 5))
    return score, reasons


def trend_stage(klines):
    """趋势阶段判断, 需要至少120天数据才可靠"""
    if not klines or len(klines) < 120: return 0, "数据不足"
    closes = [k["close"] for k in klines]
    price = closes[-1]
    ma20 = sum(closes[-20:])/20
    ma60 = sum(closes[-60:])/60
    ma120 = sum(closes[-120:])/120 if len(closes)>=120 else ma60

    # Stage 2 (上升): MA20 > MA60 > MA120 且 价格 > MA20
    if ma20 > ma60 > ma120 and price > ma20:
        return 2, "阶段2上升(强势)"
    # Stage 2 弱化版: MA20 > MA60 且 价格 > MA60
    elif ma20 > ma60 and price > ma60:
        return 2, "阶段2上升"
    # Stage 1 (筑底): 价格 > MA60 但 均线尚未多头排列
    elif price > ma60 and ma20 < ma60:
        return 1, "阶段1筑底"
    # Stage 3 (顶部): MA20 > MA60 但 价格 < MA20
    elif ma20 > ma60 and price < ma20 and price > ma60:
        return 3, "阶段3顶部"
    # Stage 4 (下降): 价格 < MA60 且 MA20 < MA60
    elif price < ma60 and ma20 < ma60:
        return 4, "阶段4下降"
    else:
        return 0, "阶段不明"


def vp_sell_signals(klines):
    """量价卖出信号检测, 来自 volume_price.py"""
    if not klines or len(klines) < 60: return []
    closes = [k["close"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    opens = [k["open"] for k in klines]
    vols = [k["volume"] for k in klines]
    price = closes[-1]

    warnings = []
    high_120 = max(closes[-120:]) if len(closes)>=120 else max(closes)
    is_high = price > high_120 * 0.85
    vol_ratio = vols[-1] / (sum(vols[-20:])/20) if sum(vols[-20:])/20>0 else 1

    body = abs(closes[-1]-opens[-1])
    upper_shadow = highs[-1] - max(opens[-1], closes[-1])
    amplitude = highs[-1] - lows[-1]

    # 1. 放量滞涨
    if is_high and vol_ratio > 1.5 and abs(closes[-1]/closes[-2]-1) < 0.005:
        warnings.append("放量滞涨(高位+放量+滞涨)")
    # 2. 缩量新高
    if price >= high_120 and vol_ratio < 0.7:
        warnings.append("缩量新高(新高+量缩)")
    # 3. 高位长上影
    if is_high and upper_shadow/(body+0.001) > 2 and closes[-1] < opens[-1]:
        warnings.append("高位长上影(上影线过长)")
    # 4. 放量大阴线
    if is_high and vol_ratio > 1.5 and closes[-1]/opens[-1]-1 < -0.03 and body/(amplitude+0.001) > 0.5:
        warnings.append("放量大阴线(高位+放量+大跌)")
    # 5. 反弹缩量
    ema20 = sum(closes[-20:])/20; ema60 = sum(closes[-60:])/60
    if ema20 < ema60 and vol_ratio < 0.7 and closes[-1] > closes[-2]:
        warnings.append("反弹缩量(下跌趋势+无量反弹)")

    return warnings


def fund_flow_score(code):
    """资金流信号"""
    flows = fetch_fund_flow(code)
    if not flows: return None, []
    total_5d = sum(f["main_net"] for f in flows[-5:])
    total_20d = sum(f["main_net"] for f in flows[-20:])
    reasons = []
    if total_5d > 5e7: reasons.append(f"主力5日净流入{total_5d/1e8:.1f}亿")
    elif total_5d < -5e7: reasons.append(f"主力5日净流出{abs(total_5d)/1e8:.1f}亿")
    if total_20d > 1e8: reasons.append(f"主力20日累计流入{total_20d/1e8:.1f}亿")
    elif total_20d < -2e8: reasons.append(f"主力20日累计流出{abs(total_20d)/1e8:.1f}亿")
    return total_5d, reasons


# ═══════════════ 综合分析 ═══════════════
def analyze_holding(code, name, htype, market, sector, quotes, klines):
    """综合多策略打分"""
    q = quotes.get(code, {})
    if not q: return None

    price = q["price"]; chg = q["chg_pct"]; pe = q["pe"]

    # ═══ 策略1: Alpha Composite (三票投票制) ═══
    cs, cs_reasons = cs_score(klines)
    dm, dm_reasons = dm_score(klines)
    stage, stage_name = trend_stage(klines)

    ac_votes = 0
    ac_details = []
    if cs >= 3: ac_votes += 1; ac_details.append(f"CAN SLIM通过({cs}/7分)")
    else: ac_details.append(f"CAN SLIM未过({cs}/7分)")
    if dm > 5: ac_votes += 1; ac_details.append("双动量通过")
    else: ac_details.append("双动量未过")
    if stage in (1,2): ac_votes += 1; ac_details.append(f"趋势通过({stage_name})")
    else: ac_details.append(f"趋势未过({stage_name})")

    # ═══ 策略2: 量价卖出信号 ═══
    sell_warnings = vp_sell_signals(klines)

    # ═══ 策略3: 资金流 ═══
    fund5d, fund_reasons = (None, []) if htype != "A" else fund_flow_score(code)

    # ═══ 估值检查 ═══
    val_warnings = []
    val_positive = []
    if pe > 0 and htype == "A":
        if pe < 15: val_positive.append(f"PE={pe:.0f}x 极低估值")
        elif pe > 150: val_warnings.append(f"PE={pe:.0f}x 极高估值")
        elif pe > 60: val_warnings.append(f"PE={pe:.0f}x 偏高")
    elif pe > 0 and 10 < pe < 30:
        val_positive.append(f"PE={pe:.0f}x 合理")

    # ═══ 综合打分 ═══
    score = 50  # 基准

    # AC投票 (25分) — 只有有足够K线数据时才生效
    has_enough_data = klines and len(klines) >= 120
    if has_enough_data:
        if ac_votes >= 3: score += 20
        elif ac_votes >= 2: score += 10
        elif ac_votes == 1: score += 0
        else: score -= 15
    else:
        ac_votes = -1  # 标记数据不足

    # 趋势阶段 (15分)
    if stage == 2: score += 15
    elif stage == 1: score += 5
    elif stage == 3: score -= 5
    elif stage == 4: score -= 15
    # stage == 0: no change

    # 量价卖出信号 (15分) — 每个卖出信号扣5分
    score -= min(15, len(sell_warnings) * 5)

    # 估值 (15分)
    if pe > 0:
        if pe < 15: score += 15
        elif pe < 30: score += 5
        elif pe > 150: score -= 15
        elif pe > 60: score -= 5

    # 当日动量 (5分)
    if chg > 3: score += 5
    elif chg < -3: score -= 5

    # 板块加成 (5分)
    hot = ["创新药","机器人","有色金属"]
    cold = ["光伏"]
    if sector in hot: score += 5
    elif sector in cold: score -= 5

    # 资金流 (10分, 仅A股)
    if fund5d is not None:
        if fund5d > 1e8: score += 10
        elif fund5d > 0: score += 3
        elif fund5d < -5e8: score -= 10
        elif fund5d < 0: score -= 3

    score = max(0, min(100, score))

    # 生成建议
    if score >= 70: action = "加仓"
    elif score >= 55: action = "持有"
    elif score >= 40: action = "观望"
    elif score >= 25: action = "减仓"
    else: action = "卖出"

    return {
        "code":code,"name":name,"type":htype,"sector":sector,
        "price":price,"chg_pct":chg,"pe":pe,"score":score,"action":action,
        "ac_votes":ac_votes,"ac_details":ac_details,
        "stage":stage,"stage_name":stage_name,
        "cs_score":cs,"cs_reasons":cs_reasons,
        "dm_score":dm,"dm_reasons":dm_reasons,
        "sell_warnings":sell_warnings,
        "fund_reasons":fund_reasons,
        "val_positive":val_positive,"val_warnings":val_warnings,
    }


# ═══════════════ 输出 ═══════════════
def print_result(r):
    """单标的结果"""
    action_icon = {"加仓":"🟢","持有":"🟢","观望":"🟡","减仓":"🟠","卖出":"🔴"}.get(r["action"],"⚪")
    chg_str = f"+{r['chg_pct']:.1f}%" if r['chg_pct']>=0 else f"{r['chg_pct']:.1f}%"
    pe_str = f"PE={r['pe']:.0f}x" if r['pe']>0 else ""

    print(f"  {action_icon} {r['action']} [{r['score']:2d}分] {r['name']}({r['code']}) | {r['price']:.2f} | {chg_str} | {pe_str}")

    # AC投票详情
    if r['ac_votes'] == -1:
        print(f"      AC投票: K线数据不足(<120日), 跳过")
    else:
        print(f"      AC投票: {' | '.join(r['ac_details'])}")
    # 趋势阶段
    print(f"      趋势: {r['stage_name']} | CS={r['cs_score']}/7 | DM={r['dm_score']:.0f}/10")

    # 正面信号
    positives = []
    if r['cs_score'] >= 3: positives.extend(r['cs_reasons'][:2])
    if r['dm_score'] > 5: positives.extend(r['dm_reasons'][:1])
    positives.extend(r['val_positive'])
    if positives: print(f"      ✅ {' | '.join(positives)}")

    # 负面信号
    negatives = []
    negatives.extend(r['sell_warnings'])
    negatives.extend(r['val_warnings'])
    negatives.extend(r['fund_reasons'][:2] if r['fund_reasons'] else [])
    if negatives: print(f"      ⚠️  {' | '.join(negatives)}")


def run():
    today = date.today().strftime("%Y-%m-%d")
    print("=" * 80)
    print(f"  每日持仓量化分析 | {today}")
    print("  策略引擎: Alpha Composite + 量价检测 + 双动量 + 趋势阶段")
    print("=" * 80)

    # 1. 拉数据
    print("\n⏳ 拉取数据...", flush=True)
    quotes = fetch_quotes()
    print(f"  行情: {len(quotes)}条", end=" | ", flush=True)

    klines_all = {}
    for code,_,htype,market,_ in HOLDINGS:
        if htype in ("ETF","A") and market in ("sh","sz"):
            kl = fetch_kline_sina(code, market, 252)
            if kl: klines_all[code] = kl
    print(f"K线: {len(klines_all)}条", flush=True)

    # 2. 分析
    results = []
    for code,name,htype,market,sector in HOLDINGS:
        r = analyze_holding(code,name,htype,market,sector,quotes,klines_all.get(code))
        if r: results.append(r)

    # 3. 输出
    groups = {
        "🟢 加仓/持有": [r for r in results if r['action'] in ("加仓","持有")],
        "🟡 观望": [r for r in results if r['action'] == "观望"],
        "🟠 减仓": [r for r in results if r['action'] == "减仓"],
        "🔴 卖出": [r for r in results if r['action'] == "卖出"],
    }

    for label, group in groups.items():
        if group:
            print(f"\n{'─'*60}")
            print(f"  {label} ({len(group)}只)")
            print(f"{'─'*60}")
            for r in sorted(group, key=lambda x: x['score'], reverse=True):
                print_result(r)

    # 4. 总结
    avg = sum(r['score'] for r in results)/len(results) if results else 0
    stage_counts = {}
    for r in results: stage_counts[r['stage_name']] = stage_counts.get(r['stage_name'],0)+1

    print(f"\n{'='*80}")
    print(f"  组合总结")
    print(f"{'='*80}")
    print(f"  平均得分: {avg:.1f}/100")
    print(f"  趋势阶段分布: {stage_counts}")
    print(f"  加仓: {', '.join(r['name'] for r in results if r['action']=='加仓') or '无'}")
    print(f"  减仓: {', '.join(r['name'] for r in results if r['action']=='减仓') or '无'}")
    print(f"  卖出: {', '.join(r['name'] for r in results if r['action']=='卖出') or '无'}")

    # 有量价卖出信号的标的
    with_warnings = [r for r in results if r['sell_warnings']]
    if with_warnings:
        print(f"\n  ⚠️ 量价卖出信号提醒:")
        for r in with_warnings:
            print(f"    {r['name']}({r['code']}): {'; '.join(r['sell_warnings'])}")

    print(f"\n  ⚠️ 免责: 策略引擎量化输出，不构成投资指令。")
    print(f"{'='*80}")


if __name__ == "__main__":
    run()
