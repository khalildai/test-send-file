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

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(ROOT, "V2.0.13-source", "data", "maturity.db")
OUT = os.path.join(ROOT, "monthly-reports", "pdf", "能力成熟度-月报-当前快照.pdf")
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

team_rows = []
for name, items in team_payloads.items():
    rate, total, delivered = score(items)
    if total:
        team_rows.append((rate, name, total, delivered))
team_rows.sort(reverse=True)

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

story.append(P("一、业务组织当前能力排名", "CJKH2"))
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
story.append(P("二、领域能力分布与短板", "CJKH2"))
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
story.append(P("三、科组明细与月度行动建议", "CJKH2"))
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
