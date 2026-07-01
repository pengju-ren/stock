#!/usr/bin/env python3
"""生成半导体产业链深度分析 PDF 报告（中文版）"""

from fpdf import FPDF
from datetime import date

FONT_PATH = "C:/Windows/Fonts/simhei.ttf"
FONT_BOLD = "C:/Windows/Fonts/simhei.ttf"

class AnalysisPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font("CJK", "", FONT_PATH)
        self.add_font("CJK", "B", FONT_BOLD)

    def header(self):
        if self.page_no() == 1:
            self.set_fill_color(15, 23, 42)
            self.rect(0, 0, 210, 38, 'F')
            self.set_font("CJK", "B", 20)
            self.set_text_color(255, 255, 255)
            self.set_y(14)
            self.cell(0, 10, "半导体产业链深度分析", align="C")
            self.ln(5)
            self.set_font("CJK", "", 12)
            self.set_text_color(96, 165, 250)
            self.cell(0, 8, "8条新闻 · 7大投资主题 · 40+标的挖掘", align="C")
            self.ln(14)

    def footer(self):
        self.set_y(-15)
        self.set_font("CJK", "", 7)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"第 {self.page_no()} 页", align="C")

    def section_title(self, title, num=""):
        self.set_fill_color(15, 23, 42)
        full = f"  {num}. {title}" if num else f"  {title}"
        self.set_font("CJK", "B", 13)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, full, fill=True)
        self.set_x(self.l_margin)
        self.ln(6)

    def sub_title(self, title):
        self.set_font("CJK", "B", 11)
        self.set_text_color(30, 64, 175)
        self.cell(0, 7, title)
        self.set_x(self.l_margin)
        self.ln(8)

    def body_text(self, text):
        self.set_font("CJK", "", 9)
        self.set_text_color(40, 40, 40)
        self.multi_cell(self.w - self.l_margin - self.r_margin, 5.5, text)
        self.ln(1)

    def bullet(self, text):
        self.set_font("CJK", "", 9)
        self.set_text_color(40, 40, 40)
        self.cell(8, 5.5, "")
        self.cell(5, 5.5, ">")
        self.set_x(self.l_margin + 13)
        self.multi_cell(self.w - self.l_margin - self.r_margin - 13, 5.5, text)

    def key_value(self, key, value, w=52):
        self.set_font("CJK", "B", 9)
        self.set_text_color(40, 40, 40)
        self.cell(w, 5.5, key)
        self.set_font("CJK", "", 9)
        self.cell(0, 5.5, value)
        self.set_x(self.l_margin)
        self.ln(6)

    def colored_box(self, text, r=230, g=240, b=255):
        self.set_fill_color(r, g, b)
        self.set_font("CJK", "B", 10)
        self.set_text_color(15, 23, 42)
        self.multi_cell(self.w - self.l_margin - self.r_margin, 6, text, fill=True)
        self.ln(2)

    def table_header(self, cols, widths):
        self.set_fill_color(30, 64, 175)
        self.set_text_color(255, 255, 255)
        self.set_font("CJK", "B", 8)
        for col, w in zip(cols, widths):
            self.cell(w, 7, " " + col, border=1, fill=True)
        self.set_x(self.l_margin)
        self.ln(8)

    def table_row(self, cells, widths, highlight=False):
        if highlight:
            self.set_fill_color(240, 245, 255)
        else:
            self.set_fill_color(255, 255, 255)
        self.set_text_color(40, 40, 40)
        self.set_font("CJK", "", 8)
        for cell, w in zip(cells, widths):
            self.cell(w, 6.5, " " + str(cell), border=1, fill=True)
        self.set_x(self.l_margin)
        self.ln(7.5)


def build_pdf():
    pdf = AnalysisPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # ── 封面信息 ──
    pdf.set_font("CJK", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 6, "研究日期: 2026-07-01  |  数据来源: Stock项目Python脚本 + 网络搜索 + 机构研报", align="C")
    pdf.set_x(pdf.l_margin)
    pdf.ln(10)

    # ═══════════════════════════
    # 总览表
    # ═══════════════════════════
    pdf.section_title("新闻→主题→标的 总览映射", "")
    headers = ["#", "新闻主题", "核心逻辑", "最受益环节", "核心标的"]
    widths = [7, 34, 36, 28, 79]
    pdf.table_header(headers, widths)
    data = [
        ["1", "微软上调人形机器人出货至5万台", "2026量产元年", "减速器/丝杠/执行器", "拓普集团(601689)、绿的谐波(688017)"],
        ["2", "探针卡/测试插座涨价", "贵金属+测试针短缺", "探针卡/测试设备", "强一股份(688809)、长川科技(300604)"],
        ["3", "国巨电容全系涨价50%", "AI虹吸高端产能", "MLCC制造+材料", "三环集团(300408)、洁美科技(002859)"],
        ["4", "Meta Vistara CXL+DDR4复用", "CXL渗透加速", "CXL芯片/接口", "澜起科技(688008)、Marvell(MRVL)"],
        ["5", "OpenAI推理成本减半", "Jevons悖论→用量暴增", "推理芯片/存储", "Broadcom(AVGO)、兆易创新(603986)"],
        ["6", "MLCC进入LTA时代", "长期协议锁价锁量", "同#3", "风华高科(000636)、国瓷材料(300285)"],
        ["7", "电网瓶颈→$BE融资5倍", "AI电力缺口", "燃料电池/电力", "Bloom Energy(BE)、三环集团(300408)"],
        ["8", "台湾OSAT涨价+瓶颈", "封测超级景气年", "封测/测试设备", "长电科技(600584)、通富微电(002156)"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(8)

    # ═══════════════════════════
    # 一、人形机器人
    # ═══════════════════════════
    pdf.section_title("人形机器人：2026量产元年", "一")
    pdf.colored_box("微软将中国2026年人形机器人出货量预期从1.4万→2.8万→5万台。特斯拉Optimus Gen3预计2026年7-8月正式投产，行业从'0→1'进入'1→10'阶段。")
    pdf.body_text("大和证券认为，执行器和灵巧手是'最具投资可操作性'的环节。摩根士丹利上调绿的谐波至增持评级。宇树科技科创板IPO仅72天过会，预计Q3挂牌。国产零部件供应链占比已达约70%，订单正从预期转化为营收。")

    pdf.sub_title("A股核心标的（按确定性排序）")
    headers = ["优先级", "标的", "代码", "PE(Fwd)", "PEG", "市值(亿)", "核心逻辑"]
    widths = [12, 26, 18, 16, 14, 20, 78]
    pdf.table_header(headers, widths)
    data = [
        ["★★★", "拓普集团", "601689", "-", "-", "-", "特斯拉T1独家执行器供应商，占整机成本>35%"],
        ["★★★", "五洲新春", "603667", "-", "-", "-", "行星滚柱丝杠核心供应商，投资11亿建98万套产能"],
        ["★★★", "绿的谐波", "688017", "400x", "8.83", "777", "谐波减速器国产龙头，单台14个，大摩增持"],
        ["★★", "兆威机电", "003021", "-", "-", "-", "灵巧手微型传动龙头，市占率30%"],
        ["★★", "双环传动", "002472", "-", "-", "-", "RV+谐波减速器双线布局"],
        ["★★", "鸣志电器", "603728", "-", "-", "-", "空心杯电机国内技术领先，起步早"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(3)
    pdf.colored_box("风险提示：绿的谐波(688017)当前PE(TTM)=568x, PEG=8.83，估值已相当昂贵，反映了极高预期。若寻求相对合理估值，可关注双环传动和五洲新春。", r=255, g=240, b=240)
    pdf.ln(6)

    # ═══════════════════════════
    # 二、探针卡/测试插座
    # ═══════════════════════════
    pdf.section_title("探针卡/测试插座：涨价+国产替代黄金窗口", "二")
    pdf.colored_box("贵金属(金/钯/铂)持续上涨 + 测试针产能严重短缺 → 探针卡成本飙升、交期延长。台湾颖崴(6515)、旺矽(6223)、中华精测(6510)已启动涨价。AI芯片测试复杂度指数级增长，国产替代迎来黄金窗口。")
    pdf.body_text("强一股份(688809)是国产探针卡绝对龙头，全球第六，MEMS探针卡打破海外垄断；长川科技(300604)是国内唯一测试机+分选机+探针台+AOI全覆盖企业；法特迪(IPO中)是测试插座+探针卡双龙头。")

    pdf.sub_title("核心标的")
    headers = ["市场", "优先级", "标的", "代码", "核心逻辑"]
    widths = [14, 14, 30, 20, 106]
    pdf.table_header(headers, widths)
    data = [
        ["A股", "★★★", "强一股份", "688809", "国产探针卡绝对龙头，全球第六，MEMS打破海外垄断，西部证券'买入'"],
        ["A股", "★★★", "长川科技", "300604", "国内唯一测试机+分选机+探针台全覆盖，华为海思独家，净利+142%"],
        ["A股", "★★", "和林微纳", "688661", "精密探针零部件，海外收入35%+，AI高端探针增量显著"],
        ["A股", "新股", "法特迪", "IPO中", "测试座+探针卡双龙头，深度绑定长电/通富/华天"],
        ["台湾", "-", "颖崴", "6515", "测试插座龙头"],
        ["台湾", "-", "旺矽", "6223", "探针卡全球主要供应商"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(6)

    # ═══════════════════════════
    # 三、MLCC超级周期
    # ═══════════════════════════
    pdf.section_title("MLCC/电容超级周期：一天一个价", "三")
    pdf.colored_box("国巨(2327)7月1日起全系电容涨价约50%，涵盖MLCC/钽电容/铝电解/聚合物/薄膜/超级电容，首次扩展至直销OEM客户。专家判断供需错配至少延续至2027-2028年。")

    pdf.sub_title("三层驱动力叠加")
    pdf.bullet("需求暴增：单台AI服务器MLCC用量是普通服务器近13倍（Blackwell约2万颗→Rubin预计超3万颗），MLCC在AI服务器BOM中跃升至第三位")
    pdf.bullet("供给挤压：村田/三星电机主动将产能转向AI/车规高端，压缩消费级通用品产能；高端产线扩产需18-24个月")
    pdf.bullet("原材料暴涨：白银、钌、钯、锡、铜大幅攀升；中国对重稀土出口管制加剧高端MLCC上游紧张")

    pdf.sub_title("涨价烈度")
    pdf.bullet("村田47μF高容MLCC现货价：300元 → 600-720元/2000颗（翻倍+），部分高容规格涨幅达3-10倍")
    pdf.bullet("风华高科电感/磁珠/压敏电阻类涨幅10-30%；国巨旗下Kemet钽电容涨幅20-30%")
    pdf.bullet("交期从10周延长至约24周（近6个月），B/B ratio维持1.3-1.4高位")

    pdf.sub_title("A股核心标的")
    headers = ["层级", "标的", "代码", "定位", "核心看点"]
    widths = [14, 28, 18, 26, 98]
    pdf.table_header(headers, widths)
    data = [
        ["制造★★★", "三环集团", "300408", "国产MLCC高端王者", "月产900亿颗，1μm/1000层技术，已入英伟达/浪潮供应链，SOFC双轮驱动"],
        ["制造★★★", "风华高科", "000636", "国产MLCC综合龙头", "全球第五，月产600亿颗，已量产220μF高容，打入AI服务器供应链"],
        ["制造★★", "达利凯普", "301566", "射频微波MLCC", "全球市占率前五、中国第一，5G/卫星通信稀缺纯正标的"],
        ["制造★★", "振华科技", "000733", "军工MLCC龙头", "军工电子核心供应商，产品毛利率远高于民用，本轮弹性最大"],
        ["材料★★★", "国瓷材料", "300285", "陶瓷粉体龙头", "国内唯一规模化量产MLCC介质粉体企业，全球市占率约15%"],
        ["材料★★★", "洁美科技", "002859", "离型膜龙头", "MLCC叠层工艺核心辅材，'卖铲子'逻辑，批量供货国巨/风华"],
        ["材料★★", "博迁新材", "605376", "镍粉龙头", "国内唯一纳米级镍粉规模化量产企业，用于MLCC内电极"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(6)

    # ═══════════════════════════
    # 四、Meta Vistara + CXL
    # ═══════════════════════════
    pdf.section_title("Meta Vistara + CXL：内存扩展新范式", "四")
    pdf.colored_box("Meta在ISCA 2026发布自研Vistara芯片，实现DDR4+DDR5 3:1混用，通过CXL 2.0实现内存池化。AI推理服务器最多减少25%，分布式缓存延迟降低29%，已部署数百万台。这是CXL大规模商用的里程碑验证！")
    pdf.body_text("瑞银预计CXL相关ASIC TAM到2030年达70-100亿美元。Meta自研ASIC仅限内部使用，不会冲击澜起/Marvell等通用CXL芯片供应商的生态位。DDR4生命周期被拉长，内存接口芯片(RCD/SPD)需求周期延长。")

    pdf.sub_title("核心标的")
    headers = ["市场", "优先级", "标的", "代码", "核心逻辑"]
    widths = [14, 14, 28, 18, 110]
    pdf.table_header(headers, widths)
    data = [
        ["A股", "★★★", "澜起科技", "688008", "全球CXL MXC芯片市占率90%+，DDR4存量复用拉长RCD/SPD生命周期。PE(TTM)=151x, PEG=3.63"],
        ["美股", "★★★", "Marvell", "MRVL", "CXL ASIC领先份额；瑞银目标价$340；预计2027年CXL收入约10亿美元"],
        ["美股", "★★", "Astera Labs", "ALAB", "Leo CXL扩展器，微软为主要客户；瑞银目标价$400"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(6)

    # ═══════════════════════════
    # 五、OpenAI推理优化
    # ═══════════════════════════
    pdf.section_title("OpenAI推理优化突破：不是利空，是利好", "五")
    pdf.colored_box("OpenAI通过软件优化将推理成本降低50%+，并与Broadcom(AVGO)合作推出自研'Jalapeño'推理芯片。市场一度恐慌'GPU需求见顶'，但费城半导体指数当日反而上涨3%。AMD +7%，Intel +7%，TSMC +3%。")
    pdf.body_text("这是18个月来第5次类似'恐慌'（DeepSeek、OpenAI资本开支修正、用户增长miss、Broadcom业绩miss、推理成本削减），每次市场都更快收复。逻辑：成本越低→用量越大→总需求越大。中国AI token日消耗已从100亿→140万亿（两年增长>1000倍）。瓶颈正从GPU训练转向推理+存储+网络。")

    pdf.sub_title("重新定价的受益者")
    headers = ["标的", "代码", "角色"]
    widths = [50, 26, 108]
    pdf.table_header(headers, widths)
    data = [
        ["Broadcom", "AVGO", "Jalapeño芯片直接合作伙伴，定制ASIC管道"],
        ["AMD", "AMD", "服务器CPU渗透AI推理（当日涨7%）"],
        ["NVIDIA", "NVDA", "仍主导训练市场；Vera Rubin(2026)目标10倍推理成本降低"],
        ["SanDisk", "-", "NAND闪存短缺，AI存储需求暴增（YTD +781%）"],
        ["兆易创新", "603986", "存储+MCU，AI推理时代存储需求爆发"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(6)

    # ═══════════════════════════
    # 六、台湾OSAT封测
    # ═══════════════════════════
    pdf.section_title("台湾OSAT封测瓶颈：涨价次数超越晶圆代工", "六")
    pdf.colored_box("日月光(3711)2026年资本支出上修至85亿美元（常年~20亿）。先进封装涨价超20%，传统封测双位数涨幅。订单能见度直通2027年以后。IC设计客户被迫签3年长约锁产能。野村证券：'史诗级供需错配将至'。")
    pdf.body_text("这是当前半导体产业链最确定的超级景气。AI驱动的封装需求从台积电CoWoS溢出至整个OSAT生态。Digitimes报道封测代工'涨价次数已超越晶圆代工业者'，后端产能成为全链条最大瓶颈。日月光全球首条经济规模FOPLP量产线2026年底投产。")

    pdf.sub_title("核心标的")
    headers = ["市场", "优先级", "标的", "代码", "PE(Fwd)", "PEG", "市值(亿)", "核心逻辑"]
    widths = [14, 14, 26, 18, 16, 14, 22, 60]
    pdf.table_header(headers, widths)
    data = [
        ["A股", "★★★", "通富微电", "002156", "72.5x", "2.84", "1122", "封测龙头，深度绑定AMD，先进封装占比持续提升"],
        ["A股", "★★★", "长电科技", "600584", "94.4x", "4.10", "1908", "国内封测No.1，技术最全面"],
        ["A股", "★★", "晶方科技", "603005", "62.7x", "2.19", "343", "影像传感封测龙头，小而美，PEG最合理"],
        ["A股", "★★", "伟测科技", "688372", "-", "-", "-", "独立第三方测试龙头"],
        ["台湾", "★★★", "日月光投控", "3711", "-", "-", "-", "全球OSAT龙头，涨价逾20%，大摩目标228元"],
        ["台湾", "★★★", "京元电子", "2449", "-", "-", "-", "专业测试龙头，大摩目标218元"],
        ["美股", "★★", "ASE Tech", "ASX", "-", "-", "1005亿$", "美股日月光，YTD+180%，美银上调估值"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(6)

    # ═══════════════════════════
    # 七、电网瓶颈 + Bloom Energy
    # ═══════════════════════════
    pdf.section_title("电网瓶颈 + Bloom Energy 250亿美元融资框架", "七")
    pdf.colored_box("Brookfield将Bloom Energy AI电力合作框架从50亿→250亿美元（5倍）。AI数据中心电网接入需5-10年，BE燃料电池可数月内部署。Oracle签约高达2.8GW。BE股价YTD+275%，12个月+1300%。")
    pdf.body_text("这验证了BE从清洁能源公司向AI核心基础设施供应商的转型。250亿是融资框架而非确定收入，存在执行风险，但需求信号明确：电力，而非芯片，正在成为AI最大的瓶颈。")

    pdf.sub_title("核心标的")
    headers = ["市场", "标的", "代码", "核心逻辑"]
    widths = [14, 38, 18, 114]
    pdf.table_header(headers, widths)
    data = [
        ["美股", "Bloom Energy", "BE", "直接受益，250亿美元融资框架，YTD+275%，Evercore目标价$350"],
        ["A股", "三环集团", "300408", "SOFC固体氧化物燃料电池+MLCC双轮驱动，与BE相同技术路线"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(8)

    # ═══════════════════════════
    # 综合标的池
    # ═══════════════════════════
    pdf.section_title("综合标的池（按优先级排序）", "")

    pdf.sub_title("Tier 1 — 逻辑最确定、估值相对合理")
    headers = ["标的", "代码", "对应新闻", "核心逻辑", "PEG"]
    widths = [28, 18, 16, 102, 16]
    pdf.table_header(headers, widths)
    data = [
        ["三环集团", "300408", "#3,#7", "MLCC涨价+SOFC燃料电池双轮驱动", "-"],
        ["通富微电", "002156", "#8", "封测涨价+AMD深度绑定", "2.84"],
        ["洁美科技", "002859", "#3,#6", "MLCC离型膜'卖铲子'，间接受益涨价潮", "-"],
        ["澜起科技", "688008", "#4", "CXL MXC芯片全球90%市占率", "3.63"],
        ["沪电股份", "002463", "#8", "PCB/载板，AI服务器核心，PEG合理", "0.94"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(3)

    pdf.sub_title("Tier 2 — 高成长但估值已高")
    headers = ["标的", "代码", "对应新闻", "核心逻辑", "PEG"]
    widths = [28, 18, 16, 102, 16]
    pdf.table_header(headers, widths)
    data = [
        ["强一股份", "688809", "#2", "国产探针卡唯一纯正龙头", "-"],
        ["长川科技", "300604", "#2,#8", "测试设备全覆盖，华为海思供应商", "-"],
        ["风华高科", "000636", "#3,#6", "MLCC全球第五，已量产220μF高容", "-"],
        ["中际旭创", "300308", "#5", "光模块龙头，AI推理需求持续拉动", "0.62"],
        ["拓普集团", "601689", "#1", "机器人执行器T1供应商", "-"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(3)

    pdf.sub_title("Tier 3 — 高弹性/题材类")
    headers = ["标的", "代码", "对应新闻", "核心逻辑"]
    widths = [28, 18, 16, 122]
    pdf.table_header(headers, widths)
    data = [
        ["五洲新春", "603667", "#1", "行星滚柱丝杠核心供应商，投资11亿建产能"],
        ["达利凯普", "301566", "#3", "射频微波MLCC稀缺纯正标的，5G/卫星通信"],
        ["晶方科技", "603005", "#8", "封测小而美，PEG=2.19估值相对合理"],
        ["博迁新材", "605376", "#3", "国内唯一纳米级镍粉量产，MLCC内电极刚需"],
        ["绿的谐波", "688017", "#1", "谐波减速器龙头（但PEG=8.83偏贵）"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(8)

    # ═══════════════════════════
    # 风险提示
    # ═══════════════════════════
    pdf.section_title("风险提示", "")
    pdf.bullet("估值过热风险：半导体板块A股平均PE(TTM)=182x，多处历史高位，回调压力不可忽视")
    pdf.bullet("MLCC周期特性：历史上MLCC涨价周期通常持续12-18个月，需密切关注拐点信号")
    pdf.bullet("人形机器人量产不确定性：5万台预期可能因技术瓶颈/供应链问题延迟")
    pdf.bullet("地缘政治风险：台湾OSAT标的面临台海局势不确定性")
    pdf.bullet("电容涨价传导风险：消费电子客户接受度存疑，涨价未必能完全转嫁")
    pdf.bullet("Bloom Energy执行风险：250亿美元是融资框架而非已承诺收入")
    pdf.bullet("OpenAI效率悖论：若AI需求弹性<1，硬件增长将减速（当前市场赌弹性>1）")
    pdf.ln(6)

    pdf.colored_box("核心结论：8条新闻共同指向一个清晰的投资主线——AI算力需求正以超乎预期的速度重塑整个半导体供应链，从上游的MLCC电容、探针卡，到中游的封测、CXL内存，再到下游的机器人、电力基础设施。瓶颈已从'GPU不够'扩散到'什么都缺'——电容、测试针、封测产能、电网接入全线告急。'瓶颈在哪里，机会就在哪里。'", r=230, g=240, b=255)
    pdf.ln(6)

    # 免责声明
    pdf.set_font("CJK", "", 7)
    pdf.set_text_color(128, 128, 128)
    pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin, 4,
        "免责声明：本报告由AI辅助分析生成，基于2026年7月1日前公开信息整理，不构成投资建议。"
        "所有估值、目标价、评级数据可能快速变化。投资决策前请自行进行尽职调查。市场投资有风险，可能导致本金亏损。"
        "数据来源：东方财富、腾讯财经、新浪财经、同花顺、mootdx、Yahoo Finance、摩根士丹利/瑞银/野村/大和等机构研报。")

    # 保存
    output_path = "e:/work/stock/semiconductor_deep_analysis_20260701.pdf"
    pdf.output(output_path)
    print(f"PDF已保存至: {output_path}")
    return output_path


if __name__ == "__main__":
    build_pdf()
