import os
import json
import sqlite3
from collections import defaultdict
from datetime import date
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak, SimpleDocTemplate
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle, Polygon, Wedge

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "output", "pdf", "能力成熟度-月报-V2-业界对标版.pdf")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
DB = os.path.join(ROOT, "github-test-send-file", "V2.0.13-source", "data", "maturity.db")
if not os.path.exists(DB):
    DB = os.path.join(ROOT, "V2.0.13-source", "data", "maturity.db")
conn = sqlite3.connect(DB)
units = {r[0]: (r[1], r[2]) for r in conn.execute("select id,kind,name from org_units")}
teams = {r[0]: r[1] for r in conn.execute("select id,name from teams")}
rels = defaultdict(list)
for org_id, team_id in conn.execute("select org_id,team_id from org_team_relations"):
    rels[org_id].append(team_id)
items = [json.loads(r[0]) for r in conn.execute("select payload from capabilities")]
conn.close()
domain_org = defaultdict(list)
for org_id, (kind, org_name) in units.items():
    if kind not in ("department", "business"):
        continue
    linked = {teams[t] for t in rels.get(org_id, []) if t in teams}
    for domain in sorted({x.get("domain", "未分类") for x in items if x.get("team") in linked}):
        subset = [x for x in items if x.get("team") in linked and x.get("domain", "未分类") == domain]
        if subset:
            done = sum(x.get("achieved") in (1, True, "1") for x in subset)
            domain_org[domain].append((done / len(subset) * 100, org_name, len(subset) - done))
for domain in domain_org:
    domain_org[domain].sort(reverse=True)
dimensions = defaultdict(lambda: [0, 0]); levels = defaultdict(lambda: [0, 0])
for item in items:
    dim = item.get("dimension", "未分类"); lvl = str(item.get("level", "未分级")); dimensions[dim][0] += 1; dimensions[dim][1] += int(item.get("achieved") in (1, True, "1")); levels[lvl][0] += 1; levels[lvl][1] += int(item.get("achieved") in (1, True, "1"))
font = next((p for p in ["/System/Library/Fonts/Supplemental/Songti.ttc", "/System/Library/Fonts/STHeiti Medium.ttc", "/Library/Fonts/Arial Unicode.ttf"] if os.path.exists(p)), None)
if not font:
    raise RuntimeError("No CJK font")
pdfmetrics.registerFont(TTFont("ReportCJK", font))
NAVY = colors.HexColor("#12233F")
BLUE = colors.HexColor("#155EEF")
PALE = colors.HexColor("#EEF4FF")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="T", parent=styles["Title"], fontName="ReportCJK", fontSize=21, leading=27, textColor=NAVY, spaceAfter=7))
styles.add(ParagraphStyle(name="H", parent=styles["Heading2"], fontName="ReportCJK", fontSize=14, leading=18, textColor=NAVY, spaceBefore=7, spaceAfter=7))
styles.add(ParagraphStyle(name="B", parent=styles["BodyText"], fontName="ReportCJK", fontSize=9.2, leading=14, textColor=colors.HexColor("#344054")))
styles.add(ParagraphStyle(name="S", parent=styles["BodyText"], fontName="ReportCJK", fontSize=7.8, leading=10.5, textColor=colors.HexColor("#667085")))
styles.add(ParagraphStyle(name="C", parent=styles["BodyText"], fontName="ReportCJK", fontSize=8.2, leading=10.5, textColor=colors.HexColor("#1D2939")))
styles.add(ParagraphStyle(name="CW", parent=styles["BodyText"], fontName="ReportCJK", fontSize=8.2, leading=10.5, textColor=colors.white))

def P(value, style="B"):
    return Paragraph(str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), styles[style])

def hf(canvas, doc):
    canvas.saveState(); canvas.setStrokeColor(colors.HexColor("#D0D5DD")); canvas.line(18*mm, 14*mm, 192*mm, 14*mm)
    canvas.setFont("ReportCJK", 7.5); canvas.setFillColor(colors.HexColor("#667085")); canvas.drawString(18*mm, 9*mm, "测试能力成熟度 - 业界对标版")
    canvas.drawRightString(192*mm, 9*mm, f"第 {doc.page} 页"); canvas.restoreState()

def bar_chart(title, labels, values, width=420, height=175, color=BLUE):
    d = Drawing(width, height); d.add(String(0, height - 14, title, fontName="ReportCJK", fontSize=10, fillColor=NAVY))
    left, bottom, chart_w, chart_h = 58, 28, width - 70, height - 54; maxv = max(max(values or [1]), 1)
    d.add(Line(left, bottom, left, bottom + chart_h, strokeColor=colors.HexColor("#98A2B3"))); d.add(Line(left, bottom, left + chart_w, bottom, strokeColor=colors.HexColor("#98A2B3")))
    for i, (label, value) in enumerate(zip(labels, values)):
        x = left + (i + .5) * chart_w / max(len(labels), 1); h = chart_h * value / maxv
        d.add(Rect(x - 13, bottom, 26, h, fillColor=color, strokeColor=None)); d.add(String(x, bottom - 12, str(label)[:6], textAnchor="middle", fontName="ReportCJK", fontSize=7, fillColor=colors.HexColor("#344054"))); d.add(String(x, bottom + h + 3, f"{value:.0f}%", textAnchor="middle", fontName="ReportCJK", fontSize=7, fillColor=NAVY))
    return d

def radar_chart(title, labels, values, width=230, height=175, color=BLUE):
    import math
    d = Drawing(width, height); d.add(String(0, height - 14, title, fontName="ReportCJK", fontSize=10, fillColor=NAVY)); cx, cy, radius = width / 2, height / 2 - 4, min(width, height) / 2 - 28; n = max(len(labels), 1)
    def point(i, r):
        a = math.pi / 2 + 2 * math.pi * i / n; return cx + r * math.cos(a), cy + r * math.sin(a)
    for level in (.25, .5, .75, 1):
        d.add(Polygon([coord for i in range(n) for coord in point(i, radius * level)], fillColor=None, strokeColor=colors.HexColor("#D0D5DD"), strokeWidth=.5))
    for i, label in enumerate(labels):
        x, y = point(i, radius); d.add(Line(cx, cy, x, y, strokeColor=colors.HexColor("#D0D5DD"), strokeWidth=.5)); lx, ly = point(i, radius + 12); d.add(String(lx, ly, str(label)[:5], textAnchor="middle", fontName="ReportCJK", fontSize=7, fillColor=colors.HexColor("#344054")))
    d.add(Polygon([coord for i, value in enumerate(values) for coord in point(i, radius * max(0, min(value, 100)) / 100)], fillColor=colors.Color(.08, .37, .93, alpha=.28), strokeColor=color, strokeWidth=1.5)); return d

def donut_chart(title, achieved, total, width=230, height=175):
    d = Drawing(width, height); d.add(String(0, height - 14, title, fontName="ReportCJK", fontSize=10, fillColor=NAVY)); cx, cy, r = width / 2, height / 2 - 3, 42; ratio = achieved / total if total else 0
    d.add(Wedge(cx, cy, r, 0, 360 * ratio, fillColor=colors.HexColor("#087443"), strokeColor=colors.white)); d.add(Wedge(cx, cy, r, 360 * ratio, 360, fillColor=colors.HexColor("#FDE2E0"), strokeColor=colors.white)); d.add(Circle(cx, cy, 23, fillColor=colors.white, strokeColor=None)); d.add(String(cx, cy - 4, f"{ratio * 100:.0f}%", textAnchor="middle", fontName="ReportCJK", fontSize=12, fillColor=NAVY)); d.add(String(cx, 24, f"已达成 {achieved} / {total}", textAnchor="middle", fontName="ReportCJK", fontSize=8, fillColor=colors.HexColor("#344054"))); return d

doc = SimpleDocTemplate(OUT, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=16*mm, bottomMargin=20*mm)
story = [P("测试能力成熟度月报 - 业界对标版", "T"), P(f"报告周期：{date.today().strftime('%Y年%m月')} · 公开来源对标框架（截至 {date.today().isoformat()}）", "S"), Spacer(1, 5*mm)]
story.append(P("本版只使用可核验的公开资料作为行业参照，不把搜索摘要或未取得原文的数字扩写为企业事实。内部组织数据、行业分位和缺陷基准均分开标识；缺少同口径原始数据的字段统一标注为“待接入”。本年度目标为 3.0 分。当前能力内容覆盖软件、硬件、机械、EMC、安规、可靠性六大领域，并按评估维度和能力等级统计。", "B"))
story.append(Spacer(1, 5*mm))
domain_totals = defaultdict(lambda: [0, 0])
for item in items:
    key = item.get("domain", "未分类"); domain_totals[key][0] += 1; domain_totals[key][1] += int(item.get("achieved") in (1, True, "1"))
domain_labels = sorted(domain_totals)
domain_rates = [domain_totals[d][1] / domain_totals[d][0] * 100 if domain_totals[d][0] else 0 for d in domain_labels]
story.append(Table([[bar_chart("内部领域达成率（当前快照）", domain_labels, domain_rates), radar_chart("内部成熟度雷达", domain_labels, domain_rates)]], colWidths=[118*mm, 56*mm], style=TableStyle([("VALIGN", (0,0),(-1,-1),"TOP"), ("LEFTPADDING", (0,0),(-1,-1),0), ("RIGHTPADDING", (0,0),(-1,-1),0)])))
story.append(donut_chart("内部能力项达成构成", sum(v[1] for v in domain_totals.values()), sum(v[0] for v in domain_totals.values())))
story.append(P("图表均为企业内部当前快照；行业 P50/P75/P90 等外部数值尚未取得同口径原始数据，因此不在图中虚构，后续以“待接入”占位。", "S"))
story.append(Spacer(1, 4*mm))
story.append(PageBreak()); story.append(P("一、评估维度与能力等级分布", "H"))
story.append(P("本页先展示成熟度模型自身的结构分布，再进入业务组织比较。质量和效率仅使用成熟度能力项的假数据代理，不代表缺陷或测试执行系统数据。", "B"))
dim_labels = list(sorted(dimensions, key=lambda x: (-dimensions[x][0], x)))[:10]; level_labels = sorted(levels, key=lambda x: (x == "未分级", x))
dist_table = [[P("评估维度", "CW"), P("能力项", "CW"), P("已达成", "CW"), P("达成率", "CW")]]
for label in dim_labels:
    total, done = dimensions[label]; dist_table.append([P(label, "C"), P(total, "C"), P(done, "C"), P(f"{done / total * 100:.1f}%", "C")])
dist = Table(dist_table, colWidths=[76*mm, 30*mm, 30*mm, 34*mm], repeatRows=1); dist.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,0), NAVY), ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.white, colors.HexColor("#F8FAFC")]), ("GRID", (0,0),(-1,-1), .35, colors.HexColor("#D0D5DD")), ("VALIGN", (0,0),(-1,-1), "MIDDLE")]))
story.append(dist); story.append(Spacer(1, 5*mm))
story.append(Table([[bar_chart("评估维度能力项数量", dim_labels, [dimensions[x][0] for x in dim_labels]), bar_chart("能力等级达成率", level_labels, [levels[x][1] / levels[x][0] * 100 if levels[x][0] else 0 for x in level_labels], width=220, color=colors.HexColor("#087443"))]], colWidths=[118*mm, 56*mm], style=TableStyle([("VALIGN", (0,0),(-1,-1),"TOP"), ("LEFTPADDING", (0,0),(-1,-1),0), ("RIGHTPADDING", (0,0),(-1,-1),0)])))
story.append(Spacer(1, 4*mm)); story.append(P("二、质量、效率、能力、基准四维达成", "H"))
overall_rate = sum(v[1] for v in domain_totals.values()) / sum(v[0] for v in domain_totals.values()) * 100 if domain_totals else 0
four_rows = [[P("分析维度", "CW"), P("当前值", "CW"), P("判定/口径", "CW")], [P("质量", "C"), P(f"{overall_rate:.1f}%", "C"), P("能力项达成率代理值，不含缺陷数据", "C")], [P("效率", "C"), P(f"{sum(v[1] for v in domain_totals.values())} 项", "C"), P("本期已达成能力项数量（假数据展示）", "C")], [P("能力", "C"), P(f"{len(domain_totals)} 个领域", "C"), P("领域/维度/等级结构与组织排名", "C")], [P("基准", "C"), P("3.0 分", "C"), P("本年度内部目标线；外部基准未接入", "C")]]
four = Table(four_rows, colWidths=[35*mm, 36*mm, 99*mm], repeatRows=1); four.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,0), BLUE), ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.white, colors.HexColor("#F8FAFC")]), ("GRID", (0,0),(-1,-1), .35, colors.HexColor("#D0D5DD")), ("VALIGN", (0,0),(-1,-1), "MIDDLE")]))
story.append(four)
story.append(P("三、公开来源与可引用事实", "H"))
src = [[P("来源", "CW"), P("可引用内容", "CW"), P("在本月报中的用途", "CW")],
       [P("思码逸《2025研发效能基准报告》\n公开索引：fxbaogao.com/detail/5041640", "C"), P("公开索引确认该报告用于研发效能基准分析；完整分位数与样本口径需以原始报告为准。", "C"), P("P50/P75/P90 对标位；当前不填未核验数值。", "C")],
       [P("DevData '24 研发效能基准报告\n公开 PDF：cdn.prod.website-files.com/.../DevData24...pdf", "C"), P("报告公开 PDF 可检索，覆盖研发效能数据洞察与测试左移等主题。", "C"), P("质量工程、测试左移和趋势章节的结构参考。", "C")],
       [P("华为云 CodeArts Board 效能洞察使用指南\nsupport.huawei.com/enterprise/tr/doc/EDOC1100370571", "C"), P("公开文档列出测试用例执行通过率、测试用例总量及项目/用户质量对比等度量。", "C"), P("补充测试质量指标定义与可视化布局。", "C")]]
st = Table(src, colWidths=[52*mm, 71*mm, 49*mm], repeatRows=1)
st.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,0), NAVY), ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.white, colors.HexColor("#F8FAFC")]), ("GRID", (0,0),(-1,-1), .35, colors.HexColor("#D0D5DD")), ("VALIGN", (0,0),(-1,-1), "TOP"), ("LEFTPADDING", (0,0),(-1,-1), 5), ("RIGHTPADDING", (0,0),(-1,-1), 5), ("TOPPADDING", (0,0),(-1,-1), 5), ("BOTTOMPADDING", (0,0),(-1,-1), 5)]))
story.append(st)
story.append(Spacer(1, 4*mm)); story.append(P("来源状态：以上链接与报告名称来自公开检索结果；本版未取得思码逸完整原始 PDF，因此不复述其具体行业百分位数字。", "S"))

story.append(PageBreak()); story.append(P("四、内部成熟度指标与行业概念映射", "H"))
mapping = [[P("内部月报指标", "CW"), P("行业参照概念", "CW"), P("外部来源", "CW"), P("状态", "CW")],
           [P("组织成熟度得分\n2级达成率×2 + 3级 + 4级", "C"), P("组织/团队效能基准分位", "C"), P("思码逸基准报告", "C"), P("待接入同口径分位", "C")],
           [P("能力项达成率、领域交付率", "C"), P("交付效能、吞吐和趋势", "C"), P("DevData '24", "C"), P("内部可算；外部不填数", "C")],
           [P("未达成能力与短板", "C"), P("研发质量、缺陷与质量基线", "C"), P("思码逸 / CodeArts Board", "C"), P("内部事实；外部定义参考", "C")],
           [P("评估维度分布", "C"), P("测试用例质量、执行通过率", "C"), P("华为云 CodeArts Board", "C"), P("需接入执行数据", "C")],
           [P("责任人、预计完成日期、验收证据", "C"), P("行动闭环与治理", "C"), P("研发效能方法论类公开资料", "C"), P("可直接落地", "C")]]
mt = Table(mapping, colWidths=[48*mm, 57*mm, 43*mm, 24*mm], repeatRows=1)
mt.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,0), BLUE), ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.white, colors.HexColor("#F8FAFC")]), ("GRID", (0,0),(-1,-1), .35, colors.HexColor("#D0D5DD")), ("VALIGN", (0,0),(-1,-1), "TOP"), ("LEFTPADDING", (0,0),(-1,-1), 5), ("RIGHTPADDING", (0,0),(-1,-1), 5), ("TOPPADDING", (0,0),(-1,-1), 5), ("BOTTOMPADDING", (0,0),(-1,-1), 5)]))
story.append(mt); story.append(Spacer(1, 6*mm))
story.append(P("五、外部版建议的页面结构", "H"))
for line in ["1. 组织总览：内部成熟度得分 + 外部基准档位（待接入时显示空位，不显示猜测值）。", "2. 质量与交付：能力达成率、领域/维度分布、测试质量指标；每个外部指标带来源、年份和适用范围。", "3. 洞察与行动：优势/短板、与基准的差距、责任人和验收证据。", "4. 数据附录：内部快照、外部来源、口径版本、样本范围、缺失项和不可比项。"]:
    story.append(P(line, "B")); story.append(Spacer(1, 1.5*mm))

story.append(PageBreak()); story.append(P("六、当前可交付的外部对标结论", "H"))
conclusions = [[P("结论", "CW"), P("证据与边界", "CW"), P("对 task #17 的动作", "CW")],
               [P("行业报告普遍采用多维度效能看板", "C"), P("CodeArts 文档明确列出研发效能、研发质量和测试用例质量等维度。", "C"), P("月报保留总览、质量、流程、行动四层结构。", "C")],
               [P("基准分位可用于对标，但必须同口径", "C"), P("思码逸报告的公开索引确认其基准属性；具体样本和分位数尚未取得原文。", "C"), P("P50/P75/P90 先做结构位，拿到原文后再填。", "C")],
               [P("测试质量指标需要额外数据源", "C"), P("CodeArts 文档给出用例通过率、总量和质量对比定义，但 V2.0.13 只读库没有这些执行事件。", "C"), P("外部版明确标注待接入，不用成熟度达成率冒充测试执行通过率。", "C")],
               [P("趋势必须来自真实月度快照", "C"), P("当前基线只有当前快照，没有可验证历史月数据。", "C"), P("V1 可用当前快照；V2 趋势待第二个月快照后启用。", "C")]]
ct = Table(conclusions, colWidths=[45*mm, 79*mm, 48*mm], repeatRows=1)
ct.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,0), NAVY), ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.white, colors.HexColor("#F8FAFC")]), ("GRID", (0,0),(-1,-1), .35, colors.HexColor("#D0D5DD")), ("VALIGN", (0,0),(-1,-1), "TOP"), ("LEFTPADDING", (0,0),(-1,-1), 5), ("RIGHTPADDING", (0,0),(-1,-1), 5), ("TOPPADDING", (0,0),(-1,-1), 5), ("BOTTOMPADDING", (0,0),(-1,-1), 5)]))
story.append(ct); story.append(Spacer(1, 7*mm)); story.append(P("外部来源链接（供复核）", "H"))
for url in ["https://www.fxbaogao.com/detail/5041640", "https://cdn.prod.website-files.com/6111eecb5937a432dabc3df4/6657352001fb47dee6bedf14_AI落地研发的最后一公里暨DevData24核心数据发布.pdf", "https://support.huawei.com/enterprise/tr/doc/EDOC1100370571?currentPartNo=k002&togo=content"]:
    story.append(P(url, "S")); story.append(Spacer(1, 1.5*mm))
story.append(Spacer(1, 4*mm)); story.append(P("本版数据原则：外部来源只用于解释指标和提供对标框架；任何未能从公开原文核验的数值均不纳入计算。", "S"))
story.append(PageBreak()); story.append(P("七、业务组织优势/劣势与外部参照", "H"))
story.append(P("本页的业务得分来自 V2.0.13 当前快照，仅用于展示内部组织洞察；外部来源只提供指标定义和行业参照，不替代内部事实。", "S"))
ins = [[P("领域", "CW"), P("业务组织排名", "CW"), P("优势/劣势", "CW"), P("外部参照与改进建议", "CW")]]
for domain in sorted(domain_org):
    ranked = domain_org[domain]
    if not ranked: continue
    top = ranked[0]; bottom = ranked[-1]
    rank_text = "；".join(f"{i+1}. {name} {rate:.1f}%" for i, (rate, name, _) in enumerate(ranked[:5]))
    gap = f"优势：{top[1]}；劣势：{bottom[1]}（未达成 {bottom[2]} 项）"
    advice = "先补齐内部短板，再接入同口径测试执行率/质量数据；CodeArts 文档可作为测试质量字段定义参照。"
    ins.append([P(domain, "C"), P(rank_text, "C"), P(gap, "C"), P(advice, "C")])
it = Table(ins, colWidths=[25*mm, 48*mm, 48*mm, 51*mm], repeatRows=1)
it.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,0), BLUE), ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.white, colors.HexColor("#F8FAFC")]), ("GRID", (0,0),(-1,-1), .35, colors.HexColor("#D0D5DD")), ("VALIGN", (0,0),(-1,-1), "TOP"), ("LEFTPADDING", (0,0),(-1,-1), 5), ("RIGHTPADDING", (0,0),(-1,-1), 5), ("TOPPADDING", (0,0),(-1,-1), 5), ("BOTTOMPADDING", (0,0),(-1,-1), 5)]))
story.append(it); story.append(Spacer(1, 5*mm)); story.append(P("外部版行动优先级", "H"))
for text in ["第一优先：围绕每个领域最低排名组织，确认未达成能力、责任人、预计完成日期和验收证据。", "第二优先：建立月度快照后再计算内部环比；不要用行业报告的总体数据替代本企业趋势。", "第三优先：补接测试用例执行率、缺陷质量等外部参照所需数据，并记录来源、年份、样本范围和可比性。"]:
    story.append(P(text, "B")); story.append(Spacer(1, 1.5*mm))
doc.build(story, onFirstPage=hf, onLaterPages=hf)
print(OUT)
