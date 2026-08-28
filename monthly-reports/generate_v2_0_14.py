import json, sqlite3
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'V2.0.14-source' / 'data' / 'maturity.db'
OUT = Path(__file__).resolve().parent / 'v2.0.14'
OUT.mkdir(exist_ok=True)
with sqlite3.connect(DB) as db:
    rows = [json.loads(r[0]) for r in db.execute('select payload from capabilities order by rowid')]

def esc(v):
    return str(v or '').replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')
def rate(items):
    return round(sum(int(x.get('achieved') or 0) for x in items) / len(items) * 100, 1) if items else 0
def score(items):
    vals = [x for x in items if x.get('level') in ('2级','3级','4级')]
    if not vals: return None
    return round(sum((int(x.get('achieved') or 0) * (2 if x.get('level') == '2级' else 1)) for x in vals) / len(vals), 2)
def group(key):
    out=[]
    for name in sorted({x.get(key) for x in rows if x.get(key)}):
        items=[x for x in rows if x.get(key)==name]; out.append({'name':name,'score':score(items),'rate':rate(items),'n':len(items)})
    return out
domains=[]
for name in sorted({x.get('domain') for x in rows if x.get('domain')}):
    items=[x for x in rows if x.get('domain')==name]; domains.append({'name':name,'score':score(items),'rate':rate(items),'n':len(items)})
overall={'score':score(rows),'rate':rate(rows),'n':len(rows),'done':sum(int(x.get('achieved') or 0) for x in rows)}
payload=json.dumps({'rows':rows,'overall':overall,'domains':domains,'depts':group('dept'),'business':group('business')},ensure_ascii=False).replace('</','<\\/')
html=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>测试能力成熟度月报 V2.0.14</title>
<style>body{{margin:0;background:#eef2f6;color:#1d2b3a;font:14px Arial,"Microsoft YaHei",sans-serif}}main{{max-width:1180px;margin:auto;padding:24px}}header{{background:#173b63;color:white;padding:28px 32px;border-radius:8px}}h1{{margin:0 0 8px;font-size:28px}}h2{{color:#173b63;margin:26px 0 10px}}.muted{{color:#647488;font-size:12px}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.card,.panel{{background:#fff;border:1px solid #d7e0e8;border-radius:6px;padding:16px}}.card b{{display:block;color:#173b63;font-size:25px;margin-top:4px}}.bar{{height:10px;background:#e5ebf0;border-radius:2px;overflow:hidden;margin-top:7px}}.bar i{{display:block;height:100%;background:#287a8d}}table{{width:100%;border-collapse:collapse;background:#fff}}th,td{{padding:9px;border-bottom:1px solid #e4e9ee;text-align:left}}th{{background:#f1f5f8;color:#44576a;font-size:12px}}.score{{font-weight:700;color:#173b63}}.two{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.tag{{display:inline-block;padding:3px 7px;background:#eef5f7;border:1px solid #c8dfe3;border-radius:3px;margin:2px;font-size:12px}}@media(max-width:720px){{main{{padding:12px}}.grid,.two{{grid-template-columns:1fr 1fr}}h1{{font-size:22px}}}}@media print{{body{{background:#fff}}main{{padding:0}}header,.panel,.card{{box-shadow:none}}}}</style>
<main><header><h1>测试能力成熟度月报</h1><div>V2.0.14 独立快照 · 截止 {date.today().isoformat()}</div><p>数据源：V2.0.14 独立数据库；本报告只读生成，不修改正式业务版本。</p></header>
<h2>一、总体成熟度达成概览</h2><div class="grid"><div class="card">总体实际得分<b>{overall['score'] if overall['score'] is not None else '—'}</b><span class="muted">目标 3.0</span></div><div class="card">能力达成率<b>{overall['rate']}%</b><span class="muted">{overall['done']} / {overall['n']} 项</span></div><div class="card">距目标差距<b>{('+' if overall['score'] and overall['score']>=3 else '') + ('—' if overall['score'] is None else f"{overall['score']-3:.2f}")}</b><span class="muted">实际得分 - 3.0</span></div><div class="card">未达成能力<b>{overall['n']-overall['done']}</b><span class="muted">待改进范围</span></div></div>
<h2>二、总体得分构成、基准与趋势</h2><section class="panel"><p>当前实际得分按 V2.0.14 事实计算；年度目标固定为 3.0；预测得分仅在存在计划月份时计算。当前数据库无完整历史月度快照，历史月份实际值标记为“待接入”，不虚构趋势。</p><div class="two"><div><h3>领域平均得分</h3>{''.join(f'<div><b>{esc(x["name"])}</b> <span class="score">{x["score"] if x["score"] is not None else "—"}</span><div class="bar"><i style="width:{min(100,(x["score"] or 0)/3*100):.0f}%"></i></div></div>' for x in domains)}</div><div><h3>领域达成率</h3>{''.join(f'<span class="tag">{esc(x["name"])} {x["rate"]}%</span>' for x in domains)}</div></div></section>
<h2>三、总体得分的部门分解与改进计划</h2><section class="panel"><table><thead><tr><th>部门</th><th>当前得分</th><th>达成率</th><th>能力项数</th><th>目标差距</th><th>改进计划</th></tr></thead><tbody>{''.join(f'<tr><td>{esc(x["name"])}</td><td class="score">{x["score"] if x["score"] is not None else "—"}</td><td>{x["rate"]}%</td><td>{x["n"]}</td><td>{"—" if x["score"] is None else f"{x["score"]-3:.2f}"}</td><td>按部门短板制定 / 待制定</td></tr>' for x in group('dept'))}</tbody></table></section>
<h2>四、总体得分的业务分解与改进计划</h2><section class="panel"><table><thead><tr><th>业务线</th><th>当前得分</th><th>达成率</th><th>能力项数</th><th>目标差距</th><th>改进计划</th></tr></thead><tbody>{''.join(f'<tr><td>{esc(x["name"])}</td><td class="score">{x["score"] if x["score"] is not None else "—"}</td><td>{x["rate"]}%</td><td>{x["n"]}</td><td>{"—" if x["score"] is None else f"{x["score"]-3:.2f}"}</td><td>按业务短板制定 / 待制定</td></tr>' for x in group('business'))}</tbody></table></section>
<h2>五、指标口径与数据附录</h2><section class="panel"><p><b>评分公式：</b>2级达成率 × 2 + 3级达成率 + 4级达成率。部门/业务线按关联科组聚合；当前实际得分不包含计划项。预测得分在接入计划月份后，按“计划月份不晚于目标月份”的未达成项累计计算。</p><p class="muted">统计范围：{overall['n']} 条能力记录，已达成 {overall['done']} 条；快照日期：{date.today().isoformat()}；报告版本：V2.0.14。历史趋势和外部基准数据待接入，不作虚构。</p></section></main>
<script>const report={payload};console.log('V2.0.14 report',report.overall);</script></html>'''
path=OUT/'测试能力成熟度月报-V2.0.14-当前快照.html'; path.write_text(html,encoding='utf-8'); print(path)
