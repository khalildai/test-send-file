import os
from datetime import date
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, PageBreak, SimpleDocTemplate

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "monthly-reports", "pdf", "能力成熟度-月报-V2-业界对标版.pdf")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
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

doc = SimpleDocTemplate(OUT, pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=16*mm, bottomMargin=20*mm)
story = [P("测试能力成熟度月报 - 业界对标版", "T"), P(f"报告周期：{date.today().strftime('%Y年%m月')} · 公开来源对标框架（截至 {date.today().isoformat()}）", "S"), Spacer(1, 5*mm)]
story.append(P("本版只使用可核验的公开资料作为行业参照，不把搜索摘要或未取得原文的数字扩写为企业事实。内部组织数据、行业分位和缺陷基准均分开标识；缺少同口径原始数据的字段统一标注为“待接入”。", "B"))
story.append(Spacer(1, 5*mm))
story.append(P("一、公开来源与可引用事实", "H"))
src = [[P("来源", "CW"), P("可引用内容", "CW"), P("在本月报中的用途", "CW")],
       [P("思码逸《2025研发效能基准报告》\n公开索引：fxbaogao.com/detail/5041640", "C"), P("公开索引确认该报告用于研发效能基准分析；完整分位数与样本口径需以原始报告为准。", "C"), P("P50/P75/P90 对标位；当前不填未核验数值。", "C")],
       [P("DevData '24 研发效能基准报告\n公开 PDF：cdn.prod.website-files.com/.../DevData24...pdf", "C"), P("报告公开 PDF 可检索，覆盖研发效能数据洞察与测试左移等主题。", "C"), P("质量工程、测试左移和趋势章节的结构参考。", "C")],
       [P("华为云 CodeArts Board 效能洞察使用指南\nsupport.huawei.com/enterprise/tr/doc/EDOC1100370571", "C"), P("公开文档列出测试用例执行通过率、测试用例总量及项目/用户质量对比等度量。", "C"), P("补充测试质量指标定义与可视化布局。", "C")]]
st = Table(src, colWidths=[52*mm, 71*mm, 49*mm], repeatRows=1)
st.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,0), NAVY), ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.white, colors.HexColor("#F8FAFC")]), ("GRID", (0,0),(-1,-1), .35, colors.HexColor("#D0D5DD")), ("VALIGN", (0,0),(-1,-1), "TOP"), ("LEFTPADDING", (0,0),(-1,-1), 5), ("RIGHTPADDING", (0,0),(-1,-1), 5), ("TOPPADDING", (0,0),(-1,-1), 5), ("BOTTOMPADDING", (0,0),(-1,-1), 5)]))
story.append(st)
story.append(Spacer(1, 4*mm)); story.append(P("来源状态：以上链接与报告名称来自公开检索结果；本版未取得思码逸完整原始 PDF，因此不复述其具体行业百分位数字。", "S"))

story.append(PageBreak()); story.append(P("二、内部成熟度指标与行业概念映射", "H"))
mapping = [[P("内部月报指标", "CW"), P("行业参照概念", "CW"), P("外部来源", "CW"), P("状态", "CW")],
           [P("组织成熟度得分\n2级达成率×2 + 3级 + 4级", "C"), P("组织/团队效能基准分位", "C"), P("思码逸基准报告", "C"), P("待接入同口径分位", "C")],
           [P("能力项达成率、领域交付率", "C"), P("交付效能、吞吐和趋势", "C"), P("DevData '24", "C"), P("内部可算；外部不填数", "C")],
           [P("未达成能力与短板", "C"), P("研发质量、缺陷与质量基线", "C"), P("思码逸 / CodeArts Board", "C"), P("内部事实；外部定义参考", "C")],
           [P("评估维度分布", "C"), P("测试用例质量、执行通过率", "C"), P("华为云 CodeArts Board", "C"), P("需接入执行数据", "C")],
           [P("责任人、预计完成日期、验收证据", "C"), P("行动闭环与治理", "C"), P("研发效能方法论类公开资料", "C"), P("可直接落地", "C")]]
mt = Table(mapping, colWidths=[48*mm, 57*mm, 43*mm, 24*mm], repeatRows=1)
mt.setStyle(TableStyle([("BACKGROUND", (0,0),(-1,0), BLUE), ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.white, colors.HexColor("#F8FAFC")]), ("GRID", (0,0),(-1,-1), .35, colors.HexColor("#D0D5DD")), ("VALIGN", (0,0),(-1,-1), "TOP"), ("LEFTPADDING", (0,0),(-1,-1), 5), ("RIGHTPADDING", (0,0),(-1,-1), 5), ("TOPPADDING", (0,0),(-1,-1), 5), ("BOTTOMPADDING", (0,0),(-1,-1), 5)]))
story.append(mt); story.append(Spacer(1, 6*mm))
story.append(P("三、外部版建议的页面结构", "H"))
for line in ["1. 组织总览：内部成熟度得分 + 外部基准档位（待接入时显示空位，不显示猜测值）。", "2. 质量与交付：能力达成率、领域/维度分布、测试质量指标；每个外部指标带来源、年份和适用范围。", "3. 洞察与行动：优势/短板、与基准的差距、责任人和验收证据。", "4. 数据附录：内部快照、外部来源、口径版本、样本范围、缺失项和不可比项。"]:
    story.append(P(line, "B")); story.append(Spacer(1, 1.5*mm))

story.append(PageBreak()); story.append(P("四、当前可交付的外部对标结论", "H"))
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
doc.build(story, onFirstPage=hf, onLaterPages=hf)
print(OUT)
