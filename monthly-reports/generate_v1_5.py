#!/usr/bin/env python3
"""Generate independent, data-driven v1.5 HTML reports from sealed V2.0.13 DB."""
import argparse, html, json, os, sqlite3
from collections import Counter
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(os.path.dirname(ROOT), "V2.0.13-source", "data", "maturity.db")
OUT = os.path.join(ROOT, "v1.5")
WEIGHTS = {"2级": 2, "3级": 1, "4级": 1}

def load():
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    rows = [json.loads(r["payload"]) for r in db.execute("select payload from capabilities order by rowid")]
    teams = [{"id": r["id"], "name": r["name"], "domains": json.loads(r["domains"] or "[]")} for r in db.execute("select id,name,domains from teams order by rowid")]
    units = list(db.execute("select id,kind,name from org_units order by rowid"))
    rel = {}
    for r in db.execute("select org_id,team_id from org_team_relations order by rowid"):
        rel.setdefault(r["org_id"], []).append(r["team_id"])
    config = {"teams": teams, "departments": [], "businesses": []}
    for r in units:
        if r["kind"] in ("department", "business"):
            config["departments" if r["kind"] == "department" else "businesses"].append({"id": r["id"], "name": r["name"], "teamIds": rel.get(r["id"], [])})
    db.close()
    return rows, config

def metric_data(rows, config):
    dims = sorted({str(r.get("dimension") or "") for r in rows if r.get("dimension")})
    by_name = {str(t["id"]): t for t in config["teams"]}
    def team_metric(team, domain, dim):
        matching = [r for r in rows if r.get("team") == team["name"] and r.get("domain") == domain and r.get("dimension") == dim and r.get("level") in WEIGHTS]
        if not matching: return None
        levels = {}
        score = 0.0
        for level, weight in WEIGHTS.items():
            subset = [r for r in matching if r.get("level") == level]
            achieved = sum(int(r.get("achieved") or 0) == 1 for r in subset)
            levels[level] = {"achieved": achieved, "total": len(subset), "weight": weight}
            score += (achieved / len(subset) * weight) if subset else 0
        return {"scope":"team", "entityId":team["id"], "entity":team["name"], "domain":domain, "dimension":dim, "score":round(score,4), "levels":levels, "capabilityCount":len(matching)}
    team_metrics=[]
    for team in config["teams"]:
        for domain in team.get("domains") or []:
            for dim in dims:
                item=team_metric(team,domain,dim)
                if item: team_metrics.append(item)
    def aggregate(kind, units):
        out=[]
        for unit in units:
            names={by_name[str(tid)]["name"] for tid in unit.get("teamIds",[]) if str(tid) in by_name}
            pairs={(x["domain"],x["dimension"]) for x in team_metrics if x["entity"] in names}
            for domain,dim in sorted(pairs):
                sample=[x for x in team_metrics if x["entity"] in names and x["domain"]==domain and x["dimension"]==dim]
                out.append({"scope":kind,"entityId":unit["id"],"entity":unit["name"],"domain":domain,"dimension":dim,"score":round(sum(x["score"] for x in sample)/len(sample),4),"teamCount":len(sample),"teams":[x["entity"] for x in sample]})
        return out
    depts=aggregate("department",config["departments"]); businesses=aggregate("business",config["businesses"])
    return {"target":3.0,"maximum":4.0,"formula":"2级达成率×2 + 3级达成率 + 4级达成率","team":team_metrics,"department":depts,"business":businesses,"averages":{}}

def build_payload(rows, config):
    metrics=metric_data(rows,config)
    for scope in ("team","department","business"):
        vals=metrics[scope]; pairs={(x["domain"],x["dimension"]) for x in vals}
        metrics["averages"][scope]=[{"scope":scope,"domain":d,"dimension":dim,"score":round(sum(x["score"] for x in vals if x["domain"]==d and x["dimension"]==dim)/len([x for x in vals if x["domain"]==d and x["dimension"]==dim]),4),"sampleCount":len([x for x in vals if x["domain"]==d and x["dimension"]==dim])} for d,dim in sorted(pairs)]
    done=sum(int(r.get("achieved") or 0)==1 for r in rows)
    return {"version":"V2.0.13","generated":date.today().isoformat(),"rows":rows,"config":config,"metrics":metrics,"summary":{"capabilities":len(rows),"achieved":done,"teams":len(config["teams"]),"departments":len(config["departments"]),"businesses":len(config["businesses"])}}

CSS = """
:root{--ink:#182b49;--muted:#65758b;--line:#d8e0ea;--bg:#f4f7fb;--blue:#2368d1;--teal:#087f6a;--red:#b42318;--amber:#b76e00}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 Arial,'Microsoft YaHei',sans-serif}main{max-width:1220px;margin:auto;padding:24px}.hero{background:#17365d;color:white;padding:28px 32px;border-radius:8px}.hero h1{margin:0 0 6px;font-size:28px}.hero p{margin:4px 0;color:#dbeafe}.note{margin-top:16px;padding:10px 14px;border-left:3px solid #77b4ff;background:#ffffff18}.controls,.grid{display:grid;gap:14px;margin:16px 0}.controls{grid-template-columns:repeat(4,1fr);background:white;padding:16px;border:1px solid var(--line);border-radius:8px}.controls label{color:var(--muted);font-size:12px}.controls select{display:block;width:100%;margin-top:4px;padding:8px;border:1px solid var(--line);border-radius:4px;background:white}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:16px 0}.kpi,.panel{background:white;border:1px solid var(--line);border-radius:8px;padding:18px}.kpi small,.caption{color:var(--muted)}.kpi strong{display:block;font-size:27px;margin:6px 0}.grid{grid-template-columns:1fr 1fr}.panel h2{font-size:18px;margin:0 0 12px}.bars{display:grid;gap:10px}.bar{display:grid;grid-template-columns:90px 1fr 55px;gap:8px;align-items:center}.track{height:14px;background:#e7edf5;border-radius:3px;overflow:hidden}.fill{height:100%;background:var(--blue)}.fill.low{background:var(--red)}table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:9px 8px;border-bottom:1px solid var(--line);text-align:left}th{background:var(--ink);color:white}tr:nth-child(even){background:#f8fafc}.tag{padding:2px 7px;border-radius:4px;font-size:12px}.good{background:#d5f5e8;color:#086044}.warn{background:#fff1c2;color:#7a4d00}.bad{background:#fee4e2;color:#912018}.tabs{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:12px;border-bottom:1px solid var(--line)}button{padding:8px 12px;border:0;background:transparent;color:var(--muted);cursor:pointer}button.active{color:var(--blue);border-bottom:3px solid var(--blue)}.tabpane{display:none}.tabpane.active{display:block}.footer{color:var(--muted);font-size:12px;margin-top:18px}@media(max-width:800px){main{padding:12px}.controls,.grid{grid-template-columns:1fr}.kpis{grid-template-columns:repeat(2,1fr)}.hero h1{font-size:23px}}
"""

def render(payload, external=False):
    blob=json.dumps(payload,ensure_ascii=False).replace("</","<\\/")
    title="测试能力成熟度 · 业界对标分析报告" if external else "测试能力成熟度 · 管理筛选分析报告"
    scope="外部参考版（展示代理已明确标注）" if external else "内部管理版（V2.0.13 事实数据）"
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{CSS}</style></head><body><main><section class="hero"><h1>{title}</h1><p>v1.5 · {scope} · 生成于 {payload["generated"]}</p><p>数据底座：V2.0.13 只读能力成熟度快照　|　目标：3.0 / 满分：4.0</p><div class="note">报告由管理筛选范围和 V2.0.13 共享指标逻辑生成，不是网页导出。公式：2级达成率×2 + 3级达成率 + 4级达成率。{("外部 P50/P75/P90 为展示代理，不代表真实行业样本。" if external else "缺陷数、逃逸率、变更失败率等当前不可得数据不纳入报告。")}</div></section><section class="controls"><div><label>组织层级</label><select id="scope"><option value="business">业务线</option><option value="department">部门</option><option value="team">科组</option></select></div><div><label>组织筛选</label><select id="entity"><option value="all">全部</option></select></div><div><label>领域筛选</label><select id="domain"><option value="all">全部领域</option></select></div><div><label>评估维度</label><select id="dimension"><option value="all">全部维度</option></select></div></section><section class="kpis"><div class="kpi"><small>能力项</small><strong id="capCount">-</strong><small>当前快照</small></div><div class="kpi"><small>已达成</small><strong id="doneCount">-</strong><small>能力事实</small></div><div class="kpi"><small>当前范围平均分</small><strong id="avgScore">-</strong><small>V2.0.13 公式</small></div><div class="kpi"><small>距目标 3.0</small><strong id="gap">-</strong><small>筛选范围</small></div></section><section class="grid"><div class="panel"><h2>领域达成分布</h2><div id="domainBars" class="bars"></div><p class="caption">仅关联且存在能力项的领域进入计算。</p></div><div class="panel"><h2>等级分布</h2><div id="levelBars" class="bars"></div><p class="caption">等级分布展示全部能力项；总分仅使用 2/3/4 级。</p></div></section><section class="panel"><div class="tabs"><button class="active" data-tab="ranking">组织排名</button><button data-tab="detail">优势与短板</button><button data-tab="method">样本与口径</button><button data-tab="plan">改进建议</button></div><div id="ranking" class="tabpane active"><table><thead><tr><th>排名 / 组织</th><th>指标数</th><th>成熟度得分</th><th>目标差距</th><th>判断</th></tr></thead><tbody id="rankingBody"></tbody></table></div><div id="detail" class="tabpane"><table><thead><tr><th>领域 · 评估维度</th><th>得分</th><th>与目标差距</th><th>状态</th></tr></thead><tbody id="detailBody"></tbody></table></div><div id="method" class="tabpane"><p>样本周期：{payload["generated"]} 当前快照；样本范围：V2.0.13 中已配置组织关系和能力项；统计对象：科组、部门、业务线。</p><p>指标定义：每个组织 × 领域 × 评估维度按 2/3/4 级达成率加权，权重为 2/1/1；部门和业务线为关联科组指标的算术平均。未关联领域不进入分母。</p><p>数据边界：本报告不推断缺陷数、逃逸率、吞吐、交付周期、变更失败率等外部运营结果。</p></div><div id="plan" class="tabpane"><p>优先处理当前筛选范围内低于 3.0 的领域与评估维度，按最低得分排序确定责任科组和验收证据。</p><p>保留本报告快照作为后续周期基线；新增真实快照后再计算趋势，不使用伪造环比数据。</p></div></section><p class="footer">独立报告 v1.5 · V2.0.13 正式版本未修改 · {('外部参考代理版' if external else '内部事实数据版')}</p></main><script>const P={blob};const M=P.metrics;const $=id=>document.getElementById(id);function opts(){{const s=$("scope").value,es=[{{id:"all",entity:"全部"}},...M[s].map(x=>({{id:x.entityId,entity:x.entity}})).filter((x,i,a)=>a.findIndex(y=>y.id===x.id)===i)];$("entity").innerHTML=es.map(x=>`<option value="${{x.id}}">${{x.entity}}</option>`).join("");const ds=[...new Set(P.rows.map(x=>x.domain).filter(Boolean))],di=[...new Set(P.rows.map(x=>x.dimension).filter(Boolean))];$("domain").innerHTML='<option value="all">全部领域</option>'+ds.map(x=>`<option>${{x}}</option>`).join("");$("dimension").innerHTML='<option value="all">全部维度</option>'+di.map(x=>`<option>${{x}}</option>`).join("");render()}}function filtered(){{const s=$("scope").value,e=$("entity").value,d=$("domain").value,i=$("dimension").value;return M[s].filter(x=>(e==='all'||String(x.entityId)===e)&&(d==='all'||x.domain===d)&&(i==='all'||x.dimension===i))}}function render(){{const a=filtered(),groups={{}};a.forEach(x=>(groups[x.domain]??=[]).push(x.score));const bars=Object.entries(groups).map(([k,v])=>[k,v.reduce((x,y)=>x+y,0)/v.length]);$("domainBars").innerHTML=bars.map(([k,v])=>`<div class="bar"><span>${{k}}</span><div class="track"><div class="fill ${{v<2.5?'low':''}}" style="width:${{Math.min(100,v/4*100)}}%"></div></div><b>${{v.toFixed(2)}}</b></div>`).join("")||'<span class="caption">当前筛选无指标</span>';const base=P.rows.filter(x=>($("domain").value==='all'||x.domain===$("domain").value)&&($("dimension").value==='all'||x.dimension===$("dimension").value));const levels={{}};base.forEach(x=>{{levels[x.level]=(levels[x.level]||[0,0]);levels[x.level][0]++;levels[x.level][1]+=Number(x.achieved||0)===1}});$("levelBars").innerHTML=Object.entries(levels).sort().map(([k,v])=>`<div class="bar"><span>${{k}}</span><div class="track"><div class="fill" style="width:${{v[1]/v[0]*100}}%"></div></div><b>${{v[1]}}/${{v[0]}}</b></div>`).join("");const score=a.length?a.reduce((x,y)=>x+y.score,0)/a.length:0;$("capCount").textContent=base.length;$("doneCount").textContent=base.filter(x=>Number(x.achieved||0)===1).length;$("avgScore").textContent=a.length?score.toFixed(2):'-';$("gap").textContent=a.length?(score-3).toFixed(2):'-';$("rankingBody").innerHTML=[...new Set(a.map(x=>x.entityId))].map(id=>{{const r=a.filter(x=>x.entityId===id),s=r.reduce((x,y)=>x+y.score,0)/r.length;return{{id,name:r[0].entity,score:s,count:r.length}}}}).sort((x,y)=>y.score-x.score).map((r,n)=>`<tr><td>${{n+1}}. ${{r.name}}</td><td>${{r.count}}</td><td>${{r.score.toFixed(2)}}</td><td>${{(r.score-3).toFixed(2)}}</td><td><span class="tag ${{r.score>=3?'good':r.score>=2.5?'warn':'bad'}}">${{r.score>=3?'达标':r.score>=2.5?'发展':'短板'}}</span></td></tr>`).join("")||'<tr><td colspan="5">当前筛选无可计算组织</td></tr>';$("detailBody").innerHTML=a.sort((x,y)=>x.score-y.score).map(r=>`<tr><td>${{r.domain}} · ${{r.dimension}}</td><td>${{r.score.toFixed(2)}}</td><td>${{(r.score-3).toFixed(2)}}</td><td><span class="tag ${{r.score>=3?'good':r.score>=2.5?'warn':'bad'}}">${{r.score>=3?'优势/达标':r.score>=2.5?'关注':'短板'}}</span></td></tr>`).join("")}}$("scope").addEventListener("change",opts);["entity","domain","dimension"].forEach(id=>$(id).addEventListener("change",render));document.querySelectorAll("[data-tab]").forEach(b=>b.addEventListener("click",()=>{{document.querySelectorAll("[data-tab],.tabpane").forEach(x=>x.classList.remove("active"));b.classList.add("active");$(b.dataset.tab).classList.add("active")}}));opts();</script></body></html>'''

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--out",default=OUT); args=ap.parse_args(); rows,config=load(); payload=build_payload(rows,config); os.makedirs(args.out,exist_ok=True)
    for external,name in ((False,"能力成熟度-管理筛选分析报告.html"),(True,"能力成熟度-业界对标分析报告.html")):
        with open(os.path.join(args.out,name),"w",encoding="utf-8") as f:f.write(render(payload,external))
    with open(os.path.join(args.out,"snapshot.json"),"w",encoding="utf-8") as f:json.dump(payload,f,ensure_ascii=False,indent=2)
    print(json.dumps({"out":args.out,"capabilities":len(rows),"team_metrics":len(payload["metrics"]["team"]),"department_metrics":len(payload["metrics"]["department"]),"business_metrics":len(payload["metrics"]["business"])},ensure_ascii=False))
if __name__=="__main__":main()
