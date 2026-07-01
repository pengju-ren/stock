#!/usr/bin/env python3
"""生成半导体产业链深度分析 PDF 报告"""

from fpdf import FPDF
from datetime import date

# Register Chinese-capable font
FONT_PATH = "C:/Windows/Fonts/simhei.ttf"

class AnalysisPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font("CJK", "", FONT_PATH)
        self.add_font("CJK", "B", "C:/Windows/Fonts/simsunb.ttf")

    def header(self):
        if self.page_no() == 1:
            self.set_fill_color(15, 23, 42)
            self.rect(0, 0, 210, 38, 'F')
            self.set_font("CJK", "B", 22)
            self.set_text_color(255, 255, 255)
            self.set_y(18)
            self.cell(0, 10, "Semiconductor Industry Chain", align="C")
            self.ln(4)
            self.set_font("CJK", "B", 14)
            self.set_text_color(96, 165, 250)
            self.cell(0, 8, "Deep Analysis & Investment Targets", align="C")
            self.ln(14)
        else:
            self.set_font("CJK", "", 7)
            self.set_text_color(100, 100, 100)
            self.cell(0, 5, "Semiconductor Deep Analysis | 2026-07-01", align="R")
            self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("CJK", "", 7)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, title, num=""):
        self.set_fill_color(15, 23, 42)
        if num:
            full = f"  {num}. {title}"
        else:
            full = f"  {title}"
        self.set_font("CJK", "B", 14)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, full, fill=True, ln=True)
        self.ln(3)

    def sub_title(self, title):
        self.set_font("CJK", "B", 11)
        self.set_text_color(30, 64, 175)
        self.cell(0, 7, title, ln=True)
        self.ln(1)

    def body_text(self, text):
        self.set_font("CJK", "", 9)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 5, text)
        self.ln(1)

    def bullet(self, text, indent=10):
        self.set_font("CJK", "", 9)
        self.set_text_color(40, 40, 40)
        self.cell(indent, 5, "")
        bullet_char = ">"
        self.cell(5, 5, bullet_char)
        self.set_x(self.l_margin + indent + 5)
        self.multi_cell(self.w - self.l_margin - self.r_margin - indent - 5, 5, text)

    def key_value(self, key, value, w=45):
        self.set_font("CJK", "B", 9)
        self.set_text_color(40, 40, 40)
        self.cell(w, 5, key + ":")
        self.set_font("CJK", "", 9)
        self.cell(0, 5, value, ln=True)

    def colored_box(self, text, r=230, g=240, b=255):
        self.set_fill_color(r, g, b)
        self.set_font("CJK", "B", 10)
        self.set_text_color(15, 23, 42)
        self.multi_cell(0, 6, text, fill=True)
        self.ln(2)

    def table_header(self, cols, widths):
        self.set_fill_color(30, 64, 175)
        self.set_text_color(255, 255, 255)
        self.set_font("CJK", "B", 8)
        for i, (col, w) in enumerate(zip(cols, widths)):
            self.cell(w, 7, " " + col, border=1, fill=True)
        self.ln()

    def table_row(self, cells, widths, highlight=False):
        if highlight:
            self.set_fill_color(240, 245, 255)
        else:
            self.set_fill_color(255, 255, 255)
        self.set_text_color(40, 40, 40)
        self.set_font("CJK", "", 8)
        for cell, w in zip(cells, widths):
            self.cell(w, 6, " " + str(cell), border=1, fill=True)
        self.ln()


def build_pdf():
    pdf = AnalysisPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # ── Cover / intro ──
    pdf.set_font("CJK", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 6, f"Research Date: 2026-07-01  |  Sources: Python scripts + Web + Broker Reports", align="C")
    pdf.ln(4)
    pdf.cell(0, 6, "Coverage: 8 News Events -> 7 Investment Themes -> 40+ Stocks across A-share / Taiwan / US markets", align="C")
    pdf.ln(10)

    # ── Overview table ──
    pdf.section_title("News -> Theme -> Stock Mapping", "")
    overview_headers = ["#", "News Theme", "Core Logic", "Best Play", "Top Picks"]
    overview_widths = [6, 35, 40, 28, 75]
    pdf.table_header(overview_headers, overview_widths)
    overview_data = [
        ["1", "MS Humanoid Robot 50k", "2026 Mass Production Yr", "Reducer/Screw/Actuator", "Tuopu Group(601689), Leaderdrive(688017)"],
        ["2", "Probe Card Price Hike", "Precious Metal + Pin Shortage", "Probe Card/Test Equip", "Qiangyi(688809), Changchuan(300604)"],
        ["3", "Capacitor Price Surge", "AI siphoning high-end capacity", "MLCC Mfg/Materials", "Sanhuan(300408), Jiemei(002859)"],
        ["4", "Meta Vistara CXL+DDR4", "CXL adoption accelerating", "CXL Chip/Interface", "Montage(688008), Marvell(MRVL)"],
        ["5", "OpenAI Inference -50%", "Jevons Paradox -> usage boom", "Inference/Memory Chips", "Broadcom(AVGO), GigaDevice(603986)"],
        ["6", "MLCC enters LTA era", "Long-term lock-in pricing", "Same as #3", "Fenghua(000636), Guoci(300285)"],
        ["7", "Grid Bottleneck $BE 5x", "AI power gap", "Fuel Cell / Power", "Bloom Energy(BE), Sanhuan(300408)"],
        ["8", "Taiwan OSAT Bottleneck", "Packaging super cycle", "OSAT / Test Equipment", "JCET(600584), Tongfu(002156)"],
    ]
    for i, row in enumerate(overview_data):
        pdf.table_row(row, overview_widths, highlight=(i % 2 == 0))
    pdf.ln(8)

    # ── 1. Humanoid Robot ──
    pdf.section_title("Humanoid Robot: 2026 Mass Production Year 1", "1")
    pdf.colored_box("Microsoft revised China humanoid robot shipments: 14k -> 28k -> 50,000 units for 2026. Tesla Optimus Gen3 begins production July-Aug 2026.")
    pdf.body_text("Morgan Stanley defines 2026 as the year humanoid robots transition from '0-to-1' to '1-to-10'. The supply chain is shifting from concept validation to mass production orders. Key catalysts: Optimus Gen3 launch (Q3 2026), Unitree IPO (Q3 2026), and domestic integrator supply chain localization reaching ~70%.")

    pdf.sub_title("A-Share Core Targets (ordered by certainty)")
    headers = ["Priority", "Stock", "Code", "PE(Fwd)", "PEG", "Mkt Cap(B)", "Key Thesis"]
    widths = [12, 28, 18, 18, 14, 22, 70]
    pdf.table_header(headers, widths)
    data = [
        ["***", "Tuopu Group", "601689", "-", "-", "-", "Tesla T1 exclusive actuator supplier, >35% of BOM"],
        ["***", "Wuzhou XinChun", "603667", "-", "-", "-", "Planetary roller screw core supplier, 1.1B CNY capacity"],
        ["***", "Leaderdrive", "688017", "400x", "8.83", "77.7", "Harmonic reducer domestic #1, 14 per bot, MS upgrade"],
        ["**", "Zhaowei机电", "003021", "-", "-", "-", "Dexterous hand micro-drive leader, 30% market share"],
        ["**", "Shuanghuan传动", "002472", "-", "-", "-", "RV + harmonic reducer dual-line layout"],
        ["**", "Mingzhi电器", "603728", "-", "-", "-", "Hollow cup motor domestic tech leader"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(4)
    pdf.colored_box("Risk: Leaderdrive(688017) PE(TTM)=568x, PEG=8.83--valuation already reflects extremely high expectations.", r=255, g=240, b=240)
    pdf.ln(6)

    # ── 2. Probe Card / Test Socket ──
    pdf.section_title("Probe Card & Test Socket: Price Hike + Domestic Substitution", "2")
    pdf.colored_box("Precious metals (Au/Pd/Pt) rising + test pin capacity severely short -> probe card prices rising. WinWay(6515), MPI(6223), Chunghwa(6510) have initiated price hikes.")
    pdf.body_text("AI chip testing complexity is growing exponentially, driving probe card demand across the board. This also opens a golden window for domestic substitution as Chinese probe card makers break the overseas MEMS monopoly.")

    pdf.sub_title("Targets")
    headers = ["Market", "Priority", "Stock", "Code", "Key Thesis"]
    widths = [14, 14, 30, 20, 102]
    pdf.table_header(headers, widths)
    data = [
        ["A-share", "***", "Qiangyi Stock", "688809", "Domestic probe card #1, global #6, MEMS breakthrough, 'Buy' rating"],
        ["A-share", "***", "Changchuan Tech", "300604", "Only full-coverage tester+sorter+prober+AOI, Huawei HiSilicon supplier, +142% profit"],
        ["A-share", "**", "Helin Micro", "688661", "Precision probe components, 35%+ overseas revenue, AI high-end probe growth"],
        ["A-share", "NEW", "Fatedi", "IPO", "Test socket + probe card leader, deep ties with JCET/Tongfu/Huatian"],
        ["Taiwan", "-", "WinWay", "6515", "Test socket leader"],
        ["Taiwan", "-", "MPI", "6223", "Probe card global major supplier"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(6)

    # ── 3. MLCC Super Cycle ──
    pdf.section_title("MLCC/Capacitor Super Cycle: 'Price Changes Daily'", "3")
    pdf.colored_box("Yageo(2327) July 1 across-the-board ~50% price hike covering MLCC, tantalum, aluminum electrolytic, polymer, film, supercapacitors. First time extending to direct OEM customers. Shortage expected through 2027-2028.")

    pdf.sub_title("Three-Layer Driving Force")
    pdf.bullet("Demand explosion: AI server MLCC usage is 13x normal servers (Blackwell ~20k -> Rubin ~30k units)")
    pdf.bullet("Supply squeeze: Murata/SEMCO shifting capacity to high-margin AI, squeezing consumer-grade supply")
    pdf.bullet("Raw material spike: Silver, ruthenium, palladium, nickel surging + China rare earth export controls")

    pdf.sub_title("MLCC Price Hike Intensity")
    pdf.bullet("Murata 47uF high-cap MLCC: CNY 300 -> 720 (doubled+)")
    pdf.bullet("Some high-cap specs: 3-10x increase")
    pdf.bullet("Fenghua inductors/beads: 10-30% increase")
    pdf.bullet("Lead times extended from 10 weeks to ~24 weeks (6 months)")

    pdf.sub_title("A-Share Core Targets")
    headers = ["Tier", "Stock", "Code", "Role", "Key Thesis"]
    widths = [12, 28, 18, 24, 98]
    pdf.table_header(headers, widths)
    data = [
        ["Mfg***", "Sanhuan Group", "300408", "MLCC high-end king", "Monthly 90B units, 1um/1000-layer tech, in NVIDIA/Inspur supply chain, SOFC dual driver"],
        ["Mfg***", "Fenghua Hi-Tech", "000636", "MLCC integrated #1", "Global #5, monthly 60B units, mass production 220uF high-cap, AI server qualified"],
        ["Mfg**", "Dalicap", "301566", "RF/Microwave MLCC", "Global top-5, China #1, 5G/satcom scarce pure-play"],
        ["Mfg**", "Zhenhua Tech", "000733", "Military MLCC", "High margin military electronics, highest elasticity this cycle"],
        ["Mat***", "Guoci Material", "300285", "Ceramic powder", "Only domestic mass-producer of MLCC dielectric powder, 15% global share"],
        ["Mat***", "Jiemei Tech", "002859", "Release film", "MLCC lamination critical material, 'shovel seller', supplies Yageo/Fenghua"],
        ["Mat**", "Boqian New Mat", "605376", "Nickel powder", "Only domestic nano-nickel powder mass producer, for MLCC inner electrodes"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(6)

    # ── 4. META Vistara / CXL ──
    pdf.section_title("Meta Vistara + CXL: Memory Expansion New Paradigm", "4")
    pdf.colored_box("Meta revealed 'Vistara' self-developed ASIC at ISCA 2026: DDR4+DDR5 hybrid (3:1 ratio) via CXL 2.0 memory pooling. AI inference servers reduced by up to 25%. Deployed across millions of servers. A milestone validation for large-scale CXL commercialization!")
    pdf.body_text("UBS estimates CXL ASIC TAM reaching $7-10B by 2030. Meta's case proves the business case for CXL memory pooling + DDR4 reuse, which will accelerate industry-wide CXL adoption. Meta's ASIC is for internal use only--it won't compete with Montage/Marvell general-purpose CXL chips.")

    pdf.sub_title("Core Targets")
    headers = ["Market", "Priority", "Stock", "Code", "Logic"]
    widths = [14, 14, 28, 18, 106]
    pdf.table_header(headers, widths)
    data = [
        ["A-share", "***", "Montage Tech", "688008", "Global CXL MXC chip 90%+ share, DDR4 reuse extends RCD lifecycle. PE(TTM)=151x PEG=3.63"],
        ["US", "***", "Marvell", "MRVL", "CXL ASIC leading share; UBS PT $340; 2027E CXL rev ~$1B"],
        ["US", "**", "Astera Labs", "ALAB", "Leo CXL expander; Microsoft as main customer; UBS PT $400"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(6)

    # ── 5. OpenAI Inference Optimization ──
    pdf.section_title("OpenAI Inference Breakthrough: Not Bearish, Bullish (Jevons Paradox)", "5")
    pdf.colored_box("OpenAI cut inference costs by 50%+ via software optimization + custom 'Jalapeno' chip with Broadcom (AVGO). Market initially feared 'peak GPU demand'--but the Philadelphia Semiconductor Index rose 3% that day. AMD +7%, Intel +7%, TSMC +3%.")
    pdf.body_text("This is the 5th similar 'scare' in 18 months (DeepSeek, OpenAI capex revision, user growth miss, Broadcom whisper miss, now inference cost cut). Each time, stocks recovered faster. The logic: lower cost -> more usage -> more total demand. China's daily AI token consumption grew from 10B to 140 trillion (>1000x) in two years. The bottleneck is shifting from GPU training to inference + memory + networking.")

    pdf.sub_title("Re-rated Beneficiaries")
    headers = ["Stock", "Code", "Role"]
    widths = [45, 25, 110]
    pdf.table_header(headers, widths)
    data = [
        ["Broadcom", "AVGO", "Direct partner on Jalapeno chip, custom ASIC pipeline"],
        ["AMD", "AMD", "Server CPU penetrating AI inference (+7% on news day)"],
        ["NVIDIA", "NVDA", "Still dominates training; Vera Rubin (2026) targets 10x inference cost reduction"],
        ["SanDisk", "-", "NAND flash shortage, AI storage demand exploding (YTD +781%)"],
        ["GigaDevice", "603986", "Memory + MCU, storage demand boom in AI inference era"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(6)

    # ── 6. Taiwan OSAT ──
    pdf.section_title("Taiwan OSAT Bottleneck: Price Hike Frequency Surpasses Foundries", "6")
    pdf.colored_box("ASE (3711) 2026 capex revised to $8.5B (from ~$2B normal). Advanced packaging price hike >20%. Traditional packaging double-digit increase. Order visibility through 2027+. IC design customers forced into 3-year LTAs. Nomura: 'Epic supply-demand mismatch coming.'")
    pdf.body_text("This is the most certain super-cycle in the current semiconductor supply chain. AI-driven packaging demand is spilling over from TSMC CoWoS to the entire OSAT ecosystem. Digitimes reports OSAT price hike frequency has exceeded foundry price hikes for the first time.")

    pdf.sub_title("Targets")
    headers = ["Market", "Priority", "Stock", "Code", "PE(Fwd)", "PEG", "Mkt Cap(B)", "Thesis"]
    widths = [14, 14, 26, 18, 16, 14, 22, 56]
    pdf.table_header(headers, widths)
    data = [
        ["A-share", "***", "Tongfu Microelec", "002156", "72.5x", "2.84", "112.2", "OSAT leader, tied to AMD, advanced packaging rising"],
        ["A-share", "***", "JCET", "600584", "94.4x", "4.10", "190.8", "China OSAT #1, most comprehensive tech"],
        ["A-share", "**", "Wafer Crystal", "603005", "62.7x", "2.19", "34.3", "Image sensor packaging leader, small & beautiful"],
        ["A-share", "**", "Weice Tech", "688372", "-", "-", "-", "Independent 3rd-party test leader"],
        ["Taiwan", "***", "ASE Holdings", "3711", "-", "-", "-", "Global OSAT #1, price hike >20%, MS PT 228 TWD"],
        ["Taiwan", "***", "KYEC", "2449", "-", "-", "-", "Professional test leader, MS PT 218 TWD"],
        ["US", "**", "ASE Technology", "ASX", "-", "-", "100.5B$", "US-listed ASE, YTD +180%, BofA upgrade"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(6)

    # ── 7. Grid / Bloom Energy ──
    pdf.section_title("Grid Bottleneck + Bloom Energy $25B Financing", "7")
    pdf.colored_box("Brookfield expanded Bloom Energy AI power partnership from $5B -> $25B (5x). Grid interconnection delays of 5-10 years make on-site fuel cells (deployable in months) a critical AI infra solution. BE +275% YTD, +1300% 12-month. Oracle signed up to 2.8GW.")
    pdf.body_text("This validates BE's transition from clean-energy company to essential AI infrastructure provider. The $25B is financing capacity, not booked revenue--execution risk exists, but the demand signal is unambiguous: electricity, not chips, is becoming AI's biggest bottleneck.")

    pdf.sub_title("Targets")
    headers = ["Market", "Stock", "Code", "Logic"]
    widths = [14, 35, 18, 113]
    pdf.table_header(headers, widths)
    data = [
        ["US", "Bloom Energy", "BE", "Direct beneficiary, $25B financing framework, +275% YTD"],
        ["A-share", "Sanhuan Group", "300408", "SOFC fuel cell + MLCC dual driver, same tech path as BE"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(8)

    # ── Final: Consolidated Target Pool ──
    pdf.section_title("Consolidated Target Pool (by Priority)", "")

    pdf.sub_title("Tier 1 -- Highest Certainty, Reasonable Valuation")
    headers = ["Stock", "Code", "News#", "Core Logic", "PEG"]
    widths = [28, 18, 14, 96, 16]
    pdf.table_header(headers, widths)
    data = [
        ["Sanhuan Group", "300408", "#3,#7", "MLCC price hike + SOFC fuel cell dual driver", "-"],
        ["Tongfu Microelec", "002156", "#8", "OSAT price hike + AMD tie-up", "2.84"],
        ["Jiemei Tech", "002859", "#3,#6", "MLCC release film 'shovel seller', indirect beneficiary", "-"],
        ["Montage Tech", "688008", "#4", "CXL MXC chip 90% global share", "3.63"],
        ["Wusheng PCB", "002463", "#8", "PCB/substrate, AI server core, PEG reasonable", "0.94"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(3)

    pdf.sub_title("Tier 2 -- High Growth but Elevated Valuation")
    headers = ["Stock", "Code", "News#", "Core Logic", "PEG"]
    widths = [28, 18, 14, 96, 16]
    pdf.table_header(headers, widths)
    data = [
        ["Qiangyi Stock", "688809", "#2", "Domestic probe card only pure-play leader", "-"],
        ["Changchuan Tech", "300604", "#2,#8", "Test equipment full coverage, Huawei supplier", "-"],
        ["Fenghua Hi-Tech", "000636", "#3,#6", "MLCC global #5, mass production 220uF high-cap", "-"],
        ["Zhongji Innolight", "300308", "#5", "Optical module leader, AI inference demand", "0.62"],
        ["Tuopu Group", "601689", "#1", "Robot actuator T1 supplier", "-"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(3)

    pdf.sub_title("Tier 3 -- High Elasticity / Thematic")
    headers = ["Stock", "Code", "News#", "Core Logic"]
    widths = [28, 18, 14, 120]
    pdf.table_header(headers, widths)
    data = [
        ["Wuzhou XinChun", "603667", "#1", "Planetary roller screw core supplier"],
        ["Dalicap", "301566", "#3", "RF microwave MLCC scarce pure-play"],
        ["Wafer Crystal", "603005", "#8", "OSAT small & beautiful, PEG=2.19"],
        ["Boqian New Mat", "605376", "#3", "Only domestic nickel powder mass producer"],
        ["Leaderdrive", "688017", "#1", "Harmonic reducer leader (but PEG=8.83 expensive)"],
    ]
    for i, row in enumerate(data):
        pdf.table_row(row, widths, highlight=(i % 2 == 0))
    pdf.ln(8)

    # ── Risk Disclaimer ──
    pdf.section_title("Risk Factors", "")
    pdf.bullet("Valuation overheating: Semiconductor sector average PE(TTM)=182x, historically elevated")
    pdf.bullet("MLCC cyclicality: Historically MLCC up-cycles last 12-18 months; watch for inflection signals")
    pdf.bullet("Humanoid robot mass production uncertainty: 50k unit target may face delays from tech/supply issues")
    pdf.bullet("Geopolitical risk: Taiwan OSAT targets face cross-strait tensions")
    pdf.bullet("Capacitor price pass-through: Consumer electronics customer acceptance uncertain")
    pdf.bullet("Bloom Energy execution risk: $25B is financing framework, not committed revenue")
    pdf.bullet("OpenAI efficiency paradox: If AI demand elasticity <1, hardware growth decelerates")

    pdf.ln(6)
    pdf.colored_box("Bottom Line: 8 news items converge on one clear investment thesis -- AI compute demand is reshaping the entire semiconductor supply chain at a pace faster than expected, from upstream MLCC capacitors and probe cards, through midstream OSAT and CXL memory, to downstream robots and power infrastructure. The bottleneck has shifted from 'not enough GPUs' to 'everything is short' -- capacitors, test pins, packaging capacity, grid access are all in critical shortage. Where the bottleneck is, the opportunity lies.", r=230, g=240, b=255)

    # ── Disclaimer ──
    pdf.ln(4)
    pdf.set_font("CJK", "", 7)
    pdf.set_text_color(128, 128, 128)
    pdf.multi_cell(0, 4,
        "Disclaimer: This report is generated by AI-assisted analysis based on publicly available information as of 2026-07-01. "
        "It does not constitute investment advice. All data (valuations, price targets, ratings) may change rapidly. "
        "Please conduct your own due diligence before making any investment decisions. Market investing involves risk including potential loss of principal. "
        "Data sources: Eastmoney, Tencent Finance, Sina Finance, THS, mootdx, Yahoo Finance, broker reports (Morgan Stanley, UBS, Nomura, Daiwa, etc.).")

    # Save
    output_path = "e:/work/stock/semiconductor_deep_analysis_20260701.pdf"
    pdf.output(output_path)
    print(f"PDF saved to: {output_path}")
    return output_path


if __name__ == "__main__":
    build_pdf()
