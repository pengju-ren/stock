#!/usr/bin/env python3
"""通过HTML生成PDF报告，使用weasyprint或备用方案"""
import subprocess, sys, os

# 先尝试用最简单的方法：生成HTML，然后用Edge/Chrome headless打印
html_content = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<style>
  @page { margin: 15mm 12mm; size: A4; }
  body { font-family: "Microsoft YaHei", "SimHei", sans-serif; font-size: 10pt; color: #222; line-height: 1.6; }
  h1 { text-align: center; background: #0f172a; color: #fff; padding: 16px; margin: -15mm -12mm 6mm -12mm; font-size: 18pt; }
  h1 .sub { font-size: 11pt; color: #60a5fa; font-weight: normal; display: block; margin-top: 4px; }
  h2 { background: #0f172a; color: #fff; padding: 6px 10px; font-size: 12pt; margin: 18px 0 8px 0; }
  h3 { color: #1e40af; font-size: 11pt; margin: 14px 0 4px 0; border-bottom: 1px solid #dbeafe; padding-bottom: 3px; }
  h4 { color: #333; font-size: 10pt; margin: 10px 0 4px 0; }
  p { margin: 4px 0; }
  ul { margin: 2px 0 6px 0; padding-left: 18px; }
  li { margin: 1px 0; }
  table { width: 100%; border-collapse: collapse; margin: 6px 0 10px 0; font-size: 8.5pt; }
  th { background: #1e40af; color: #fff; padding: 5px 4px; text-align: left; font-weight: bold; }
  td { padding: 4px; border: 1px solid #d4d4d8; }
  tr:nth-child(even) td { background: #f8fafc; }
  .highlight { background: #fef3c7; padding: 6px 10px; border-left: 4px solid #f59e0b; margin: 6px 0; font-weight: bold; font-size: 9pt; }
  .info { color: #6b7280; font-size: 9pt; text-align: center; margin-bottom: 10px; }
  .risk-box { background: #fff1f2; border-left: 4px solid #e11d48; padding: 4px 10px; margin: 4px 0; font-size: 9pt; }
  .disclaimer { color: #9ca3af; font-size: 7pt; border-top: 1px solid #e5e7eb; padding-top: 8px; margin-top: 20px; }
  .page-break { page-break-before: always; }
</style>
</head>
<body>

<h1>半导体产业链深度分析<span class="sub">8条新闻 · 7大投资主题 · 40+标的挖掘</span></h1>
<p class="info">研究日期: 2026-07-01 | 数据源: Stock项目Python脚本 + 网络搜索 + 机构研报 | A股/台湾/美股全覆盖</p>

<h2>新闻 → 产业链 → 标的 总览图</h2>
<table>
<tr><th>#</th><th>新闻主题</th><th>核心逻辑</th><th>最受益环节</th><th>核心标的</th></tr>
<tr><td>1</td><td>微软上调人形机器人出货至5万台</td><td>2026量产元年</td><td>减速器/丝杠/执行器</td><td><b>拓普集团、绿的谐波</b></td></tr>
<tr><td>2</td><td>探针卡/测试插座涨价</td><td>贵金属+测试针短缺</td><td>探针卡/测试设备</td><td><b>强一股份、长川科技</b></td></tr>
<tr><td>3</td><td>电容全系涨价(国巨)</td><td>AI虹吸高端产能</td><td>MLCC制造/材料</td><td><b>三环集团、洁美科技</b></td></tr>
<tr><td>4</td><td>Meta Vistara CXL+DDR4</td><td>CXL渗透加速</td><td>CXL芯片/接口</td><td><b>澜起科技、Marvell</b></td></tr>
<tr><td>5</td><td>OpenAI推理成本减半</td><td>Jevons悖论→用量暴增</td><td>推理芯片/存储</td><td><b>Broadcom、兆易创新</b></td></tr>
<tr><td>6</td><td>MLCC进入LTA时代</td><td>长期锁价锁量</td><td>同#3</td><td><b>风华高科、国瓷材料</b></td></tr>
<tr><td>7</td><td>电网瓶颈→$BE融资5x</td><td>AI电力缺口</td><td>燃料电池/电力</td><td><b>Bloom Energy、三环集团</b></td></tr>
<tr><td>8</td><td>台湾OSAT涨价+瓶颈</td><td>封测超级景气年</td><td>封测/测试设备</td><td><b>长电科技、通富微电</b></td></tr>
</table>

<h2>一、🤖 人形机器人：2026量产元年，微软上调出货预期至5万台</h2>

<h3>核心逻辑</h3>
<p>摩根士丹利将2026年中国出货量预期从1.4万→2.8万→<b>5万台</b>，行业进入"1→10"阶段。特斯拉Optimus Gen3预计<b>2026年7-8月正式投产</b>。大和证券认为执行器和灵巧手是"最具投资可操作性"的环节。国产零部件供应链占比已达约70%，订单正从预期转化为营收。</p>

<h3>A股核心标的（按确定性排序）</h3>
<table>
<tr><th>优先级</th><th>标的</th><th>代码</th><th>PE(Fwd)</th><th>PEG</th><th>市值(亿)</th><th>逻辑</th></tr>
<tr><td>★★★</td><td><b>拓普集团</b></td><td>601689</td><td>-</td><td>-</td><td>-</td><td>Tesla T1独家执行器供应商，占整机成本>35%</td></tr>
<tr><td>★★★</td><td><b>五洲新春</b></td><td>603667</td><td>-</td><td>-</td><td>-</td><td>行星滚柱丝杠核心供应商，投资11亿建98万套产能</td></tr>
<tr><td>★★★</td><td><b>绿的谐波</b></td><td>688017</td><td>400x</td><td>8.83</td><td>777</td><td>谐波减速器国产龙头，单台14个谐波，大摩增持</td></tr>
<tr><td>★★</td><td>兆威机电</td><td>003021</td><td>-</td><td>-</td><td>-</td><td>灵巧手微型传动龙头，市占率30%</td></tr>
<tr><td>★★</td><td>双环传动</td><td>002472</td><td>-</td><td>-</td><td>-</td><td>RV+谐波减速器双线布局</td></tr>
<tr><td>★★</td><td>鸣志电器</td><td>603728</td><td>-</td><td>-</td><td>-</td><td>空心杯电机国内技术领先，起步早</td></tr>
</table>
<div class="highlight">⚠ 注意：从Python脚本实时数据看，绿的谐波(688017)当前PE(TTM)=568x, PEG=8.83——估值已相当昂贵。若寻求估值相对合理的，双环传动和五洲新春的性价比可能更高。</div>

<h2>二、🔌 探针卡/测试插座：涨价进行时，国产替代黄金窗口</h2>

<h3>核心逻辑</h3>
<ul>
<li>贵金属（金/钯/铂）价格持续上涨 → 探针卡制造成本飙升</li>
<li>测试针产能<b>严重短缺</b> → 交期延长 → 涨价传导</li>
<li>台湾WinWay(颖崴6515)、MPI(旺矽6223)、中华精测(6510)等已启动涨价</li>
<li>AI芯片测试复杂度指数级增长 → 探针卡用量暴增</li>
</ul>

<h3>核心标的</h3>
<table>
<tr><th>市场</th><th>优先级</th><th>标的</th><th>代码</th><th>逻辑</th></tr>
<tr><td>A股</td><td>★★★</td><td><b>强一股份</b></td><td>688809</td><td>国产探针卡绝对龙头，全球第六，MEMS探针卡打破海外垄断，西部证券"买入"</td></tr>
<tr><td>A股</td><td>★★★</td><td><b>长川科技</b></td><td>300604</td><td>国内唯一测试机+分选机+探针台+AOI全覆盖，华为海思独家，净利+142%</td></tr>
<tr><td>A股</td><td>★★</td><td>和林微纳</td><td>688661</td><td>精密探针零部件，海外收入35%+，AI高端探针增量</td></tr>
<tr><td>A股</td><td>新股</td><td>法特迪</td><td>IPO中</td><td>测试座/探针卡双龙头，深度绑定长电/通富/华天，辅导验收已通过</td></tr>
<tr><td>台湾</td><td>-</td><td>颖崴</td><td>6515</td><td>测试插座龙头</td></tr>
<tr><td>台湾</td><td>-</td><td>旺矽</td><td>6223</td><td>探针卡全球主要供应商</td></tr>
</table>

<h2>三、🔋 MLCC/电容：超级周期开启，"一天一个价"</h2>

<h3>核心逻辑（三层叠加）</h3>
<ol>
<li><b>需求暴增</b>：AI服务器MLCC用量是普通服务器<b>13倍</b>（Blackwell约2万颗→Rubin预计超3万颗），MLCC在AI服务器BOM中跃升至第三位</li>
<li><b>供给挤压</b>：村田/三星电机主动将产能转向AI/车规高端，压缩消费级通用品产能；高端产线扩产需18-24个月</li>
<li><b>原材料暴涨</b>：白银、钌、钯、镍价格攀升 + 中国稀土出口管制加剧高端MLCC上游紧张</li>
</ol>

<h3>MLCC涨价烈度</h3>
<table>
<tr><th>品类</th><th>涨幅</th></tr>
<tr><td>村田47μF高容MLCC现货价</td><td>¥300 → ¥600-720/2000颗（翻倍+），部分高容规格达3-10倍</td></tr>
<tr><td>国巨全系电容(7/1起)</td><td>约50%，首次扩展至直销OEM客户</td></tr>
<tr><td>风华高科电感/磁珠/压敏电阻</td><td>10-30%</td></tr>
<tr><td>交期</td><td>从10周延长至约24周（近6个月）</td></tr>
</table>
<p>专家判断：供需错配至少延续至<b>2027-2028年</b>。</p>

<h3>A股核心标的</h3>
<table>
<tr><th>层级</th><th>标的</th><th>代码</th><th>核心看点</th></tr>
<tr><td>制造★★★</td><td><b>三环集团</b></td><td>300408</td><td>MLCC+SOFC双轮驱动，月产900亿颗，1μm/1000层技术，已入英伟达/浪潮供应链</td></tr>
<tr><td>制造★★★</td><td><b>风华高科</b></td><td>000636</td><td>全球第五，月产600亿颗，已量产220μF高容，打入AI服务器供应链</td></tr>
<tr><td>制造★★</td><td>达利凯普</td><td>301566</td><td>射频微波MLCC，全球前五、中国第一，5G/卫星通信稀缺纯正标的</td></tr>
<tr><td>制造★★</td><td>振华科技</td><td>000733</td><td>军工MLCC龙头，高毛利，本轮行情弹性最大</td></tr>
<tr><td>材料★★★</td><td><b>国瓷材料</b></td><td>300285</td><td>国内唯一规模化量产MLCC介质粉体，全球市占率约15%</td></tr>
<tr><td>材料★★★</td><td><b>洁美科技</b></td><td>002859</td><td>MLCC离型膜龙头，"卖铲子"逻辑，批量供货国巨/风华，6/29涨停</td></tr>
<tr><td>材料★★</td><td>博迁新材</td><td>605376</td><td>国内唯一纳米级镍粉规模化量产，用于MLCC内电极</td></tr>
</table>

<h2>四、🧠 Meta Vistara + CXL：内存扩展新范式</h2>

<h3>核心逻辑</h3>
<p>Meta在ISCA 2026发布<b>Vistara自研芯片</b>，实现DDR4+DDR5混用（3:1配比），通过CXL 2.0实现内存池化：AI推理服务器<b>减少25%</b>，分布式缓存延迟<b>降低29%</b>，已部署<b>数百万台</b>服务器。这是CXL大规模商用的里程碑验证！</p>
<p>瑞银预计CXL相关ASIC TAM到2030年达<b>70-100亿美元</b>。Meta自研ASIC仅限内部使用，不会冲击澜起/Marvell等通用CXL芯片供应商的生态位。DDR4生命周期被拉长，内存接口芯片(RCD/SPD)需求周期延长。</p>

<h3>核心标的</h3>
<table>
<tr><th>市场</th><th>优先级</th><th>标的</th><th>代码</th><th>逻辑</th></tr>
<tr><td>A股</td><td>★★★</td><td><b>澜起科技</b></td><td>688008</td><td>全球CXL MXC芯片市占率<b>90%+</b>，DDR4存量复用拉长RCD生命周期。PE(TTM)=151x PEG=3.63</td></tr>
<tr><td>美股</td><td>★★★</td><td><b>Marvell</b></td><td>MRVL</td><td>CXL ASIC领先份额；瑞银目标$340；2027年CXL收入约10亿美元</td></tr>
<tr><td>美股</td><td>★★</td><td>Astera Labs</td><td>ALAB</td><td>Leo CXL扩展器，微软为主客户；瑞银目标$400</td></tr>
</table>

<h2>五、⚡ OpenAI推理优化：不是利空是利好（Jevons悖论）</h2>

<h3>核心逻辑</h3>
<p>OpenAI通过软件优化将推理成本减半 + 自研<b>Jalapeño芯片</b>（与AVGO合作），市场一度恐慌"GPU需求见顶"，但实际：<b>费城半导体指数当日反而上涨3%</b>。AMD +7%，Intel +7%，TSMC +3%。</p>
<p>这是18个月来第5次类似"恐慌"（DeepSeek、OpenAI资本开支修正、用户增长miss、Broadcom业绩miss、推理成本削减），每次市场都更快收复。逻辑：<b>成本越低→用量越大→总需求越大</b>。中国AI token日消耗已从100亿→<b>140万亿</b>（两年增长>1000倍）。瓶颈从GPU训练转向<b>推理 + 存储 + 网络</b>。</p>

<h3>重新定价的受益者</h3>
<table>
<tr><th>标的</th><th>代码</th><th>角色</th></tr>
<tr><td><b>Broadcom</b></td><td>AVGO</td><td>Jalapeño直接合作伙伴，定制ASIC管道</td></tr>
<tr><td><b>AMD</b></td><td>AMD</td><td>服务器CPU渗透AI推理（当日涨7%）</td></tr>
<tr><td><b>NVIDIA</b></td><td>NVDA</td><td>仍主导训练市场；Vera Rubin(2026)目标10倍推理成本降低</td></tr>
<tr><td><b>SanDisk</b></td><td>-</td><td>NAND闪存短缺，AI存储需求暴增（YTD +781%）</td></tr>
<tr><td><b>兆易创新</b></td><td>603986</td><td>存储+MCU，AI推理时代存储需求爆发</td></tr>
</table>

<h2>六、🔗 台湾OSAT封测：涨价次数超越晶圆代工</h2>

<h3>核心逻辑</h3>
<p>这是当前半导体产业链<b>最确定的超级景气</b>：</p>
<ul>
<li>日月光(3711)2026年资本支出上修至<b>85亿美元</b>（常年约20亿）</li>
<li>先进封装涨价<b>超过20%</b>，传统封测双位数涨幅</li>
<li>订单能见度直通<b>2027年以后</b></li>
<li>IC设计客户被迫签<b>3年长约</b>锁产能</li>
<li>野村证券："史诗级供需错配将至"</li>
<li>Digitimes：OSAT涨价次数已<b>超越晶圆代工</b>，后端产能成为全链条最大瓶颈</li>
</ul>

<h3>核心标的</h3>
<table>
<tr><th>市场</th><th>优先级</th><th>标的</th><th>代码</th><th>PE(Fwd)</th><th>PEG</th><th>市值(亿)</th><th>逻辑</th></tr>
<tr><td>A股</td><td>★★★</td><td><b>通富微电</b></td><td>002156</td><td>72.5x</td><td>2.84</td><td>1122</td><td>封测龙头，深度绑定AMD，先进封装占比持续提升</td></tr>
<tr><td>A股</td><td>★★★</td><td><b>长电科技</b></td><td>600584</td><td>94.4x</td><td>4.10</td><td>1908</td><td>国内封测No.1，技术最全面</td></tr>
<tr><td>A股</td><td>★★</td><td>晶方科技</td><td>603005</td><td>62.7x</td><td>2.19</td><td>343</td><td>影像传感封测龙头，小而美，PEG最合理</td></tr>
<tr><td>A股</td><td>★★</td><td>伟测科技</td><td>688372</td><td>-</td><td>-</td><td>-</td><td>独立第三方测试龙头</td></tr>
<tr><td>台湾</td><td>★★★</td><td><b>日月光投控</b></td><td>3711</td><td>-</td><td>-</td><td>-</td><td>全球OSAT龙头，涨价逾20%，大摩目标228元</td></tr>
<tr><td>台湾</td><td>★★★</td><td><b>京元电子</b></td><td>2449</td><td>-</td><td>-</td><td>-</td><td>专业测试龙头，大摩目标218元</td></tr>
<tr><td>美股</td><td>★★</td><td>ASE Tech</td><td>ASX</td><td>-</td><td>-</td><td>1005亿$</td><td>美股日月光，YTD+180%，美银上调估值</td></tr>
</table>
<div class="highlight">📊 Python实时数据：通富微电(002156) PEG=2.84，晶方科技(603005) PEG=2.19——在封测环节属于估值相对合理的标的。</div>

<h2>七、🔋 电网瓶颈 + Bloom Energy 250亿美元融资框架</h2>

<h3>$BE核心逻辑</h3>
<ul>
<li>Brookfield将Bloom Energy合作框架从50亿→<b>250亿美元</b>（5倍）</li>
<li>AI数据中心电网接入需<b>5-10年</b>，BE燃料电池可<b>数月内部署</b></li>
<li>Oracle已签约高达<b>2.8GW</b>，还有Equinix、AEP等大客户</li>
<li>BE股价YTD <b>+275%</b>，12个月 <b>+1300%</b></li>
</ul>

<h3>核心标的</h3>
<table>
<tr><th>市场</th><th>标的</th><th>代码</th><th>逻辑</th></tr>
<tr><td>美股</td><td><b>Bloom Energy</b></td><td>BE</td><td>直接受益，250亿美元融资框架，Evercore目标价$350</td></tr>
<tr><td>A股</td><td><b>三环集团</b></td><td>300408</td><td>SOFC（固体氧化物燃料电池）双轮驱动，与BE技术路线相同</td></tr>
</table>

<h2>🎯 综合：按优先级排序的核心标的池</h2>

<h3>Tier 1 —— 逻辑最确定、估值相对合理</h3>
<table>
<tr><th>标的</th><th>代码</th><th>对应新闻</th><th>核心逻辑</th><th>PEG</th></tr>
<tr><td><b>三环集团</b></td><td>300408</td><td>#3,#7</td><td>MLCC涨价+SOFC双驱动</td><td>-</td></tr>
<tr><td><b>通富微电</b></td><td>002156</td><td>#8</td><td>封测涨价+AMD绑定</td><td>2.84</td></tr>
<tr><td><b>洁美科技</b></td><td>002859</td><td>#3,#6</td><td>MLCC离型膜"卖铲子"，间接受益</td><td>-</td></tr>
<tr><td><b>澜起科技</b></td><td>688008</td><td>#4</td><td>CXL芯片90%市占率</td><td>3.63</td></tr>
<tr><td><b>沪电股份</b></td><td>002463</td><td>#8</td><td>PCB/载板，AI服务器核心</td><td>0.94</td></tr>
</table>

<h3>Tier 2 —— 高成长但估值已高</h3>
<table>
<tr><th>标的</th><th>代码</th><th>对应新闻</th><th>核心逻辑</th><th>PEG</th></tr>
<tr><td><b>强一股份</b></td><td>688809</td><td>#2</td><td>国产探针卡唯一龙头</td><td>-</td></tr>
<tr><td><b>长川科技</b></td><td>300604</td><td>#2,#8</td><td>测试设备全覆盖</td><td>-</td></tr>
<tr><td><b>风华高科</b></td><td>000636</td><td>#3,#6</td><td>MLCC全球第五</td><td>-</td></tr>
<tr><td><b>中际旭创</b></td><td>300308</td><td>#5</td><td>光模块龙头，AI推理需求</td><td>0.62</td></tr>
<tr><td><b>拓普集团</b></td><td>601689</td><td>#1</td><td>机器人执行器T1</td><td>-</td></tr>
</table>

<h3>Tier 3 —— 高弹性/题材类</h3>
<table>
<tr><th>标的</th><th>代码</th><th>对应新闻</th><th>核心逻辑</th></tr>
<tr><td><b>五洲新春</b></td><td>603667</td><td>#1</td><td>行星滚柱丝杠</td></tr>
<tr><td><b>达利凯普</b></td><td>301566</td><td>#3</td><td>射频MLCC稀缺标的</td></tr>
<tr><td><b>晶方科技</b></td><td>603005</td><td>#8</td><td>封测小而美</td></tr>
<tr><td><b>博迁新材</b></td><td>605376</td><td>#3</td><td>镍粉唯一标的</td></tr>
<tr><td><b>绿的谐波</b></td><td>688017</td><td>#1</td><td>谐波减速器龙头（但PEG=8.83偏贵）</td></tr>
</table>

<h2>⚠ 风险提示</h2>
<div class="risk-box">
<ol>
<li><b>估值过热风险</b>：半导体板块A股平均PE(TTM)=182x，多处历史高位，回调压力不可忽视</li>
<li><b>MLCC周期特性</b>：历史上MLCC涨价周期通常持续12-18个月，需密切关注拐点信号</li>
<li><b>人形机器人量产不确定性</b>：5万台预期可能因技术瓶颈/供应链问题延迟</li>
<li><b>地缘政治风险</b>：台湾OSAT标的面临台海局势不确定性</li>
<li><b>电容涨价传导风险</b>：消费电子客户接受度存疑，涨价未必能完全转嫁</li>
<li><b>Bloom Energy执行风险</b>：250亿美元是融资框架而非已承诺收入</li>
<li><b>OpenAI效率悖论</b>：若AI需求弹性<1，硬件增长将减速（当前市场赌弹性>1）</li>
</ol>
</div>

<div class="highlight">
<b>总结：</b>8条新闻共同指向一个清晰的投资主线——AI算力需求正以超乎预期的速度重塑整个半导体供应链，从上游的MLCC电容、探针卡，到中游的封测、CXL内存，再到下游的机器人、电力基础设施。当前瓶颈已从"GPU不够"扩散到"什么都缺"——电容、测试针、封测产能、电网接入全线告急。<b>"瓶颈在哪里，机会就在哪里。"</b>
</div>

<p class="disclaimer">
免责声明：本报告由AI辅助分析生成，基于2026年7月1日前公开信息整理，不构成投资建议。所有估值、目标价、评级数据可能快速变化。投资决策前请自行进行尽职调查。市场投资有风险，可能导致本金亏损。数据来源：东方财富、腾讯财经、新浪财经、同花顺、mootdx、Yahoo Finance、摩根士丹利/瑞银/野村/大和等机构研报。
</p>

</body>
</html>
'''

html_path = "e:/work/stock/report.html"
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html_content)

# Try to convert to PDF using Edge (Windows built-in)
pdf_path = "e:/work/stock/semiconductor_deep_analysis_20260701.pdf"

# Use PowerShell to print HTML to PDF via Edge
ps_script = f'''
$htmlPath = "{html_path.replace(chr(92), chr(92)+chr(92))}"
$pdfPath = "{pdf_path.replace(chr(92), chr(92)+chr(92))}"

# Use Microsoft Edge headless print-to-PDF
$edgePath = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe"
if (-not (Test-Path $edgePath)) {{
    $edgePath = "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe"
}}

if (Test-Path $edgePath) {{
    Start-Process -FilePath $edgePath -ArgumentList "--headless --disable-gpu --print-to-pdf=`"$pdfPath`" `"file:///$htmlPath`"" -Wait -NoNewWindow
    Write-Output "PDF created via Edge: $pdfPath"
}} else {{
    Write-Output "Edge not found"
}}
'''

ps_result = subprocess.run(
    ["powershell", "-Command", ps_script],
    capture_output=True, text=True, timeout=60
)
print(ps_result.stdout)
if ps_result.stderr:
    print("STDERR:", ps_result.stderr)

# Check if PDF was created
if os.path.exists(pdf_path):
    size_kb = os.path.getsize(pdf_path) / 1024
    print(f"PDF已保存: {pdf_path} ({size_kb:.0f} KB)")
else:
    print(f"PDF生成失败，HTML报告已保存至: {html_path}")
    print("请用浏览器打开HTML文件，Ctrl+P打印为PDF")
