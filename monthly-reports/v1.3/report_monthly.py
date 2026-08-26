import json
import os
import sqlite3
from collections import defaultdict
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle, Polygon, Wedge

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, "github-test-send-file", "V2.0.13-source", "data", "maturity.db")
OUT = os.path.join(ROOT, "output", "pdf", "能力成熟度-月报-当前快照.pdf")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

font_candidates = [
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]
font_path = next((p for p in font_candidates if os.path.exists(p)), None)
if not font_path:
    raise RuntimeError("No CJK-capable font found")
pdfmetrics.registerFont(TTFont("ReportCJK", font_path))

BLUE = colors.HexColor("#155EEF")
NAVY = colors.HexColor("#12233F")
PALE = colors.HexColor("#EEF4FF")
GREEN = colors.HexColor("#087443")
RED = colors.HexColor("#B42318")
AMBER = colors.HexColor("#B54708")

def esc(value):
    return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def score(payloads):
    levels = defaultdict(lambda: [0, 0])
    for row in payloads:
        levels[row.get("level", "")][0] += 1
        if row.get("achieved") in (1, True, "1"):
            levels[row.get("level", "")][1] += 1
    total = sum(v[0] for v in levels.values())
    delivered = sum(v[1] for v in levels.values())
    return (delivered / total * 100 if total else 0), total, delivered

conn = sqlite3.connect(DB)
units = {r[0]: (r[1], r[2]) for r in conn.execute("select id,kind,name from org_units")}
teams = {r[0]: r[1] for r in conn.execute("select id,name from teams")}
relations = defaultdict(list)
for org_id, team_id in conn.execute("select org_id,team_id from org_team_relations"):
    relations[org_id].append(team_id)
payloads = []
for (raw,) in conn.execute("select payload from capabilities"):
    payloads.append(json.loads(raw))
conn.close()

team_payloads = defaultdict(list)
for item in payloads:
    team_payloads[item.get("team", "")].append(item)

org_rows = []
for org_id, (kind, name) in units.items():
    if kind not in ("department", "business"):
        continue
    linked = [teams[t] for t in relations.get(org_id, []) if t in teams]
    items = [x for x in payloads if x.get("team") in linked]
    rate, total, delivered = score(items)
    if total:
        org_rows.append((rate, name, len(linked), total, delivered))
org_rows.sort(reverse=True)

domains = defaultdict(lambda: [0, 0])
for item in payloads:
    key = item.get("domain", "未分类")
    domains[key][0] += 1
    domains[key][1] += int(item.get("achieved") in (1, True, "1"))
domain_rows = sorted(domains.items(), key=lambda x: (-x[1][0], x[0]))
dimensions = defaultdict(lambda: [0, 0])
levels = defaultdict(lambda: [0, 0])
for item in payloads:
    dimensions[item.get("dimension", "未分类")][0] += 1
    dimensions[item.get("dimension", "未分类")][1] += int(item.get("achieved") in (1, True, "1"))
    levels[str(item.get("level", "未分级"))][0] += 1
    levels[str(item.get("level", "未分级"))][1] += int(item.get("achieved") in (1, True, "1"))

team_rows = []
for name, items in team_payloads.items():
    rate, total, delivered = score(items)
    if total:
        team_rows.append((rate, name, total, delivered))
team_rows.sort(reverse=True)

domain_org_rows = defaultdict(list)
for org_id, (kind, name) in units.items():
    if kind not in ("department", "business"):
        continue
    linked = [teams[t] for t in relations.get(org_id, []) if t in teams]
    for domain in sorted({x.get("domain", "未分类") for x in payloads if x.get("team") in linked}):
        items = [x for x in payloads if x.get("team") in linked and x.get("domain", "未分类") == domain]
        rate, total, delivered = score(items)
        if total:
            domain_org_rows[domain].append((rate, name, total, delivered))
for domain in domain_org_rows:
    domain_org_rows[domain].sort(reverse=True)

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="CJKTitle", parent=styles["Title"], fontName="ReportCJK", fontSize=22, leading=28, textColor=NAVY, alignment=TA_LEFT, spaceAfter=8))
styles.add(ParagraphStyle(name="CJKH2", parent=styles["Heading2"], fontName="ReportCJK", fontSize=14, leading=18, textColor=NAVY, spaceBefore=8, spaceAfter=8))
styles.add(ParagraphStyle(name="CJKBody", parent=styles["BodyText"], fontName="ReportCJK", fontSize=9.5, leading=15, textColor=colors.HexColor("#344054")))
styles.add(ParagraphStyle(name="CJKSmall", parent=styles["BodyText"], fontName="ReportCJK", fontSize=8, leading=11, textColor=colors.HexColor("#667085")))
styles.add(ParagraphStyle(name="CJKCell", parent=styles["BodyText"], fontName="ReportCJK", fontSize=8.5, leading=11, textColor=colors.HexColor("#1D2939")))
styles.add(ParagraphStyle(name="CJKCellWhite", parent=styles["BodyText"], fontName="ReportCJK", fontSize=8.5, leading=11, textColor=colors.white))

def P(text, style="CJKBody"):
    return Paragraph(esc(text), styles[style])

def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D0D5DD"))
    canvas.line(18 * mm, 14 * mm, 192 * mm, 14 * mm)
    canvas.setFont("ReportCJK", 7.5)
    canvas.setFillColor(colors.HexColor("#667085"))
    canvas.drawString(18 * mm, 9 * mm, "测试能力成熟度 · 月报当前快照")
    canvas.drawRightString(192 * mm, 9 * mm, f"第 {doc.page} 页")
    canvas.restoreState()

def kpi(label, value, note):
    return [P(label, "CJKSmall"), P(value, "CJKTitle"), P(note, "CJKSmall")]

def bar_chart(title, labels, values, width=480, height=175, color=BLUE):
    d = Drawing(width, height)
    d.add(String(0, height - 14, title, fontName="ReportCJK", fontSize=10, fillColor=NAVY))
    left, bottom, chart_w, chart_h = 58, 28, width - 70, height - 54
    maxv = max(max(values or [1]), 1)
    d.add(Line(left, bottom, left, bottom + chart_h, strokeColor=colors.HexColor("#98A2B3")))
    d.add(Line(left, bottom, left + chart_w, bottom, strokeColor=colors.HexColor("#98A2B3")))
    for i, (label, value) in enumerate(zip(labels, values)):
        x = left + (i + 0.5) * chart_w / max(len(labels), 1)
        h = chart_h * value / maxv
        d.add(Rect(x - 13, bottom, 26, h, fillColor=color, strokeColor=None))
        d.add(String(x, bottom - 12, str(label)[:6], textAnchor="middle", fontName="ReportCJK", fontSize=7, fillColor=colors.HexColor("#344054")))
        d.add(String(x, bottom + h + 3, f"{value:.0f}%", textAnchor="middle", fontName="ReportCJK", fontSize=7, fillColor=NAVY))
    return d

def radar_chart(title, labels, values, width=240, height=175, color=BLUE):
    d = Drawing(width, height)
    d.add(String(0, height - 14, title, fontName="ReportCJK", fontSize=10, fillColor=NAVY))
    cx, cy, radius = width / 2, height / 2 - 4, min(width, height) / 2 - 28
    n = max(len(labels), 1)
    def point(i, r):
        import math
        a = math.pi / 2 + 2 * math.pi * i / n
        return cx + r * math.cos(a), cy + r * math.sin(a)
    for level in (0.25, 0.5, 0.75, 1.0):
        pts = [coord for i in range(n) for coord in point(i, radius * level)]
        d.add(Polygon(pts, fillColor=None, strokeColor=colors.HexColor("#D0D5DD"), strokeWidth=.5))
    for i, label in enumerate(labels):
        x, y = point(i, radius)
        d.add(Line(cx, cy, x, y, strokeColor=colors.HexColor("#D0D5DD"), strokeWidth=.5))
        lx, ly = point(i, radius + 12)
        d.add(String(lx, ly, str(label)[:5], textAnchor="middle", fontName="ReportCJK", fontSize=7, fillColor=colors.HexColor("#344054")))
    pts = [coord for i, value in enumerate(values) for coord in point(i, radius * max(0, min(value, 100)) / 100)]
    d.add(Polygon(pts, fillColor=colors.Color(0.08, 0.37, 0.93, alpha=.28), strokeColor=color, strokeWidth=1.5))
    return d

def donut_chart(title, achieved, total, width=240, height=175):
    d = Drawing(width, height)
    d.add(String(0, height - 14, title, fontName="ReportCJK", fontSize=10, fillColor=NAVY))
    cx, cy, r = width / 2, height / 2 - 3, 42
    ratio = achieved / total if total else 0
    d.add(Wedge(cx, cy, r, 0, 360 * ratio, fillColor=GREEN, strokeColor=colors.white))
    d.add(Wedge(cx, cy, r, 360 * ratio, 360, fillColor=colors.HexColor("#FDE2E0"), strokeColor=colors.white))
    d.add(Circle(cx, cy, 23, fillColor=colors.white, strokeColor=None))
    d.add(String(cx, cy - 4, f"{ratio * 100:.0f}%", textAnchor="middle", fontName="ReportCJK", fontSize=12, fillColor=NAVY))
    d.add(String(cx, 24, f"已达成 {achieved} / {total}", textAnchor="middle", fontName="ReportCJK", fontSize=8, fillColor=colors.HexColor("#344054")))
    return d

doc = SimpleDocTemplate(OUT, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=16 * mm, bottomMargin=20 * mm)
story = []
story.append(P("测试能力成熟度月报", "CJKTitle"))
story.append(P(f"报告周期：{date.today().strftime('%Y年%m月')} · 当前快照（截至 {date.today().isoformat()}）", "CJKSmall"))
story.append(Spacer(1, 7 * mm))
story.append(P("本报告基于 V2.0.13 的能力成熟度数据结构生成，展示当前各业务组织的测试能力水平。由于现有只读基线尚未提供历史月度快照，本版不虚构环比趋势；趋势栏将在后续月度快照形成后自动补齐。", "CJKBody"))
story.append(Spacer(1, 5 * mm))

kpis = [
    kpi("组织单元", str(len(org_rows)), "部门与业务线"),
    kpi("关联科组", str(len(team_payloads)), "有能力数据的科组"),
    kpi("能力项", str(len(payloads)), "当前能力成熟度记录"),
    kpi("总体交付率", f"{sum(int(x.get('achieved') in (1, True, '1')) for x in payloads) / len(payloads) * 100:.1f}%" if payloads else "0.0%", "已达成 / 能力项"),
]
kt = Table([[x[0] for x in kpis], [x[1] for x in kpis], [x[2] for x in kpis]], colWidths=[43 * mm] * 4)
kt.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, -1), PALE), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#B2CCFF")),
    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D6E4FF")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
]))
story.append(kt)
story.append(Spacer(1, 7 * mm))

domain_rates = [v[1] / v[0] * 100 if v[0] else 0 for _, v in domain_rows]
radar = radar_chart("六大领域成熟度雷达（当前快照）", [d for d, _ in domain_rows], domain_rates, width=205, height=165)
bars = bar_chart("各领域达成率（目标：年度 3.0 分对应成熟度提升）", [d for d, _ in domain_rows], domain_rates, width=330, height=165)
donut = donut_chart("能力项达成构成", sum(int(x.get("achieved") in (1, True, "1")) for x in payloads), len(payloads))
story.append(Table([[bars, radar]], colWidths=[94 * mm, 80 * mm], style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)])))
story.append(donut)
story.append(Spacer(1, 4 * mm))
story.append(P("图表说明：柱形图和雷达图展示六大领域当前达成率，饼图展示能力项已达成与未达成构成；年度目标为 3.0 分，历史趋势待后续月度快照接入。", "CJKSmall"))
story.append(Spacer(1, 5 * mm))

story.append(PageBreak())
story.append(P("一、评估维度与能力等级分布", "CJKH2"))
story.append(P("本页先呈现能力成熟度自身的结构分布，再进入业务组织比较。质量与效率使用成熟度能力项达成结果的假数据展示，不代表缺陷或测试执行系统数据。", "CJKBody"))
dim_labels = list(sorted(dimensions, key=lambda x: (-dimensions[x][0], x)))[:10]
level_labels = sorted(levels, key=lambda x: (x == "未分级", x))
dist_table = [[P("评估维度", "CJKCellWhite"), P("能力项", "CJKCellWhite"), P("已达成", "CJKCellWhite"), P("达成率", "CJKCellWhite")]]
for label in dim_labels:
    total, done = dimensions[label]; dist_table.append([P(label, "CJKCell"), P(total, "CJKCell"), P(done, "CJKCell"), P(f"{done / total * 100:.1f}%", "CJKCell")])
dist = Table(dist_table, colWidths=[76 * mm, 30 * mm, 30 * mm, 34 * mm], repeatRows=1)
dist.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#D0D5DD")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
story.append(dist); story.append(Spacer(1, 5 * mm))
story.append(Table([[bar_chart("评估维度能力项数量", dim_labels, [dimensions[x][0] for x in dim_labels], width=420), bar_chart("能力等级达成率", level_labels, [levels[x][1] / levels[x][0] * 100 if levels[x][0] else 0 for x in level_labels], width=220, color=GREEN)]], colWidths=[118 * mm, 56 * mm], style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)])))

story.append(Spacer(1, 4 * mm)); story.append(P("二、质量、效率、能力、基准四维达成", "CJKH2"))
overall_rate = sum(v[1] for v in domains.values()) / sum(v[0] for v in domains.values()) * 100 if domains else 0
four_rows = [[P("分析维度", "CJKCellWhite"), P("当前值", "CJKCellWhite"), P("判定/口径", "CJKCellWhite")],
             [P("质量", "CJKCell"), P(f"{overall_rate:.1f}%", "CJKCell"), P("能力项达成率代理值；不含缺陷数据", "CJKCell")],
             [P("效率", "CJKCell"), P(f"{sum(int(x.get('achieved') in (1, True, '1')) for x in payloads)} 项", "CJKCell"), P("本期已达成能力项数量（假数据填充展示）", "CJKCell")],
             [P("能力", "CJKCell"), P(f"{len(domain_rows)} 个领域", "CJKCell"), P("领域/维度/等级结构与组织排名", "CJKCell")],
             [P("基准", "CJKCell"), P("3.0 分", "CJKCell"), P("本年度内部目标线；外部基准未接入", "CJKCell")]]
four = Table(four_rows, colWidths=[35 * mm, 36 * mm, 99 * mm], repeatRows=1)
four.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), BLUE), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#D0D5DD")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
story.append(four)
story.append(Spacer(1, 5 * mm)); story.append(P("三、整体研发效能与分析口径", "CJKH2"))
scope_rows = [[P("模块", "CJKCellWhite"), P("本版展示内容", "CJKCellWhite"), P("数据口径", "CJKCellWhite")],
 [P("样本与口径", "CJKCell"), P("组织、科组、能力项、领域、评估维度和等级分布", "CJKCell"), P("V2.0.13 只读快照；组织关系按当前关联计算", "CJKCell")],
 [P("整体研发效能", "CJKCell"), P("总体达成率、年度目标差距、领域结构和组织覆盖", "CJKCell"), P("成熟度能力项达成结果；历史趋势暂不虚构", "CJKCell")],
 [P("交付效率", "CJKCell"), P("已达成能力项数量、组织覆盖率、领域推进情况", "CJKCell"), P("用于展示的假数据代理，不代表研发交付周期", "CJKCell")],
 [P("交付质量", "CJKCell"), P("能力项达成、未达成缺口、短板收敛情况", "CJKCell"), P("成熟度结果代理；不含缺陷、逃逸率、回退数据", "CJKCell")],
 [P("工程效率与流程", "CJKCell"), P("评估维度覆盖、等级跃迁、自动化相关能力项", "CJKCell"), P("按能力模型记录分析，不扩展到外部执行系统", "CJKCell")],
 [P("组织协同与度量", "CJKCell"), P("业务/部门/科组排名、优势短板、改进责任", "CJKCell"), P("按组织关联科组聚合；同分并列", "CJKCell")],
 [P("基准对标", "CJKCell"), P("年度目标 3.0 分、目标差距和相对排名", "CJKCell"), P("内部目标线；外部 P50/P75/P90 不填未核验值", "CJKCell")]]
scope = Table(scope_rows, colWidths=[32 * mm, 78 * mm, 66 * mm], repeatRows=1); scope.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#D0D5DD")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
story.append(scope); story.append(Spacer(1, 4 * mm)); story.append(P("高绩效团队洞察（内部代理）：优先关注领域覆盖完整、2/3/4 级能力连续达成、跨组织关联清晰且短板项较少的科组；该结论用于成熟度改进，不等同于外部研发效能排名。", "CJKBody"))

story.append(P("三、业务组织当前能力排名", "CJKH2"))
org_data = [[P("排名 / 组织", "CJKCellWhite"), P("关联科组", "CJKCellWhite"), P("能力项", "CJKCellWhite"), P("已达成", "CJKCellWhite"), P("交付率", "CJKCellWhite")]]
for i, (rate, name, teams_n, total, delivered) in enumerate(org_rows[:12], 1):
    org_data.append([P(f"{i}. {name}", "CJKCell"), P(teams_n, "CJKCell"), P(total, "CJKCell"), P(delivered, "CJKCell"), P(f"{rate:.1f}%", "CJKCell")])
ot = Table(org_data, colWidths=[77 * mm, 24 * mm, 23 * mm, 23 * mm, 27 * mm], repeatRows=1)
ot.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D0D5DD")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]))
story.append(ot)
story.append(Spacer(1, 5 * mm))
story.append(P("解读：交付率用于快速识别当前成熟度差异；组织排名按当前关联能力项的已达成比例排序，后续月报可在同一表中追加环比变化。", "CJKSmall"))

story.append(PageBreak())
story.append(P("四、领域能力分布与短板", "CJKH2"))
domain_data = [[P("领域", "CJKCellWhite"), P("能力项", "CJKCellWhite"), P("已达成", "CJKCellWhite"), P("交付率", "CJKCellWhite"), P("关注级别", "CJKCellWhite")]]
for domain, (total, delivered) in domain_rows:
    rate = delivered / total * 100 if total else 0
    level = "优先改进" if rate < 50 else "持续跟踪" if rate < 80 else "稳定"
    domain_data.append([P(domain, "CJKCell"), P(total, "CJKCell"), P(delivered, "CJKCell"), P(f"{rate:.1f}%", "CJKCell"), P(level, "CJKCell")])
dt = Table(domain_data, colWidths=[60 * mm, 28 * mm, 28 * mm, 30 * mm, 28 * mm], repeatRows=1)
dt.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D0D5DD")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]))
story.append(dt)
story.append(Spacer(1, 7 * mm))
story.append(P("短板能力清单（当前未达成）", "CJKH2"))
gap_data = [[P("领域", "CJKCellWhite"), P("评估维度", "CJKCellWhite"), P("能力内容", "CJKCellWhite"), P("所属科组", "CJKCellWhite"), P("等级", "CJKCellWhite")]]
for item in [x for x in payloads if x.get("achieved") not in (1, True, "1")][:14]:
    gap_data.append([P(item.get("domain"), "CJKCell"), P(item.get("dimension"), "CJKCell"), P(item.get("description"), "CJKCell"), P(item.get("team"), "CJKCell"), P(item.get("level"), "CJKCell")])
gt = Table(gap_data, colWidths=[27 * mm, 32 * mm, 55 * mm, 38 * mm, 22 * mm], repeatRows=1)
gt.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7A271A")), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFF7F5"), colors.white]),
    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#F0B8AD")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]))
story.append(gt)

story.append(PageBreak())
story.append(P("五、六大领域下的业务组织排名", "CJKH2"))
story.append(P("以下排名按各业务组织在该领域关联能力项的当前达成率计算；空白组织表示当前快照没有该领域能力项，不纳入比较。", "CJKSmall"))
for domain in [x[0] for x in domain_rows]:
    story.append(Spacer(1, 2 * mm)); story.append(P(f"{domain}领域", "CJKH2"))
    rows = [[P("排名 / 业务组织", "CJKCellWhite"), P("能力项", "CJKCellWhite"), P("已达成", "CJKCellWhite"), P("领域得分", "CJKCellWhite"), P("判断", "CJKCellWhite")]]
    for i, (rate, name, total, delivered) in enumerate(domain_org_rows.get(domain, [])[:8], 1):
        judgement = "优势" if i == 1 and rate >= 80 else "重点改进" if rate < 50 else "跟踪"
        rows.append([P(f"{i}. {name}", "CJKCell"), P(total, "CJKCell"), P(delivered, "CJKCell"), P(f"{rate:.1f}%", "CJKCell"), P(judgement, "CJKCell")])
    table = Table(rows, colWidths=[76 * mm, 24 * mm, 24 * mm, 28 * mm, 24 * mm], repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NAVY), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]), ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D0D5DD")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story.append(table)

story.append(PageBreak())
story.append(P("六、各业务优势/劣势与改进计划", "CJKH2"))
story.append(P("优势取各业务组织领域达成率最高项，劣势取最低项；改进优先级综合领域达成率、未达成能力数量和能力等级缺口。", "CJKSmall"))
insight_rows = [[P("业务组织", "CJKCellWhite"), P("优势能力", "CJKCellWhite"), P("劣势能力", "CJKCellWhite"), P("优先改进计划", "CJKCellWhite")]]
for _, name, _, _, _ in org_rows:
    org_domains = []
    linked = [teams[t] for oid, ts in relations.items() if oid in units and units[oid][1] == name for t in ts if t in teams]
    for domain, vals in domain_org_rows.items():
        match = next((x for x in vals if x[1] == name), None)
        if match: org_domains.append((match[0], domain, match[2]-match[3]))
    if not org_domains: continue
    best = max(org_domains); worst = min(org_domains)
    plan = f"优先补齐{worst[1]}领域 {worst[2]} 项未达成能力，确认责任人和验收日期"
    insight_rows.append([P(name, "CJKCell"), P(f"{best[1]}（{best[0]:.1f}%）", "CJKCell"), P(f"{worst[1]}（{worst[0]:.1f}%）", "CJKCell"), P(plan, "CJKCell")])
it = Table(insight_rows, colWidths=[43 * mm, 40 * mm, 40 * mm, 53 * mm], repeatRows=1)
it.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7A271A")), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFF7F5"), colors.white]), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#F0B8AD")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
story.append(it)
story.append(Spacer(1, 5 * mm))
story.append(P("改进计划建议", "CJKH2"))
for text in ["本月：各业务确认劣势领域的未达成能力、责任人、预计完成日期和验收证据。", "下月：对本月快照重算领域排名，复核优势是否保持、劣势是否收敛，并记录新增/遗留项。", "持续：当连续两个月低于 50% 时升级为重点改进项；当领域达成率达到 80% 后转入经验复用和风险监测。"]:
    story.append(P(text, "CJKBody")); story.append(Spacer(1, 2 * mm))

story.append(PageBreak())
story.append(P("七、科组明细与行动跟踪", "CJKH2"))
team_data = [[P("科组", "CJKCellWhite"), P("能力项", "CJKCellWhite"), P("已达成", "CJKCellWhite"), P("交付率", "CJKCellWhite"), P("建议", "CJKCellWhite")]]
for rate, name, total, delivered in team_rows[:18]:
    advice = "优先补齐未达成项" if rate < 50 else "保持交付节奏" if rate < 80 else "总结可复制做法"
    team_data.append([P(name, "CJKCell"), P(total, "CJKCell"), P(delivered, "CJKCell"), P(f"{rate:.1f}%", "CJKCell"), P(advice, "CJKCell")])
tt = Table(team_data, colWidths=[65 * mm, 25 * mm, 25 * mm, 27 * mm, 32 * mm], repeatRows=1)
tt.setStyle(TableStyle([
    ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D0D5DD")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
]))
story.append(tt)
story.append(Spacer(1, 6 * mm))
story.append(P("月度行动建议", "CJKH2"))
for text in [
    "1. 由各业务组织确认本月未达成能力项的责任人、预计完成日期和验收证据。",
    "2. 优先处理交付率低于 50% 的领域与科组，月末复盘未达成原因并更新行动记录。",
    "3. 下月保留本报告快照，与本月结果对账后增加环比、趋势和目标偏差。",
]:
    story.append(P(text, "CJKBody"))
    story.append(Spacer(1, 2 * mm))
story.append(Spacer(1, 5 * mm))
story.append(P("数据说明：本报告读取 V2.0.13 只读基线 maturity.db，仅用于独立月报输出；未写回正式系统，也未改变业务数据。", "CJKSmall"))

doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
print(OUT)
