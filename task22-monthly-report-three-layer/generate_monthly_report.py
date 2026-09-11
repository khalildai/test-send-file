#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试能力成熟度月报生成脚本（单文件 HTML）。

只读数据，不写库。优先读 5000 /api/state，否则读 SQLite。

用法：
  python generate_monthly_report.py
  python generate_monthly_report.py --api http://127.0.0.1:5000/api/state
  python generate_monthly_report.py --db E:\\raft\\V2.0.29\\data\\maturity.db
  python generate_monthly_report.py --out 月报.html
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import re
import sqlite3
import sys
import html as htmlmod
from datetime import date
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

CAPABILITY_DOMAINS = ["软件", "硬件", "机械", "EMC", "合规", "环境可靠性"]
WEIGHTS = {"2级": 2, "3级": 1, "4级": 1}
FORECAST_MONTH = 12


def parse_json(value, fallback):
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def load_state_from_db(path: str) -> dict:
    connection = sqlite3.connect(path, timeout=15)
    connection.row_factory = sqlite3.Row
    db = connection
    settings = {row["key"]: parse_json(row["value"], None) for row in db.execute("SELECT key, value FROM app_settings")}
    teams = [{"id": row["id"], "name": row["name"], "domains": parse_json(row["domains"], [])} for row in db.execute("SELECT id, name, domains FROM teams ORDER BY rowid")]
    units = list(db.execute("SELECT id, kind, name FROM org_units ORDER BY rowid"))
    relations = {}
    for row in db.execute("SELECT org_id, team_id FROM org_team_relations ORDER BY rowid"):
        relations.setdefault(row["org_id"], []).append(row["team_id"])
    config = {
        "teams": teams,
        "departments": [{"id": row["id"], "name": row["name"], "teamIds": relations.get(row["id"], [])} for row in units if row["kind"] == "department"],
        "businesses": [{"id": row["id"], "name": row["name"], "teamIds": relations.get(row["id"], [])} for row in units if row["kind"] == "business"],
        "retiredTeamIds": settings.get("retiredTeamIds") or [],
        "retiredDeptIds": settings.get("retiredDeptIds") or [],
        "retiredBusinessIds": settings.get("retiredBusinessIds") or [],
    }
    rev_row = db.execute("SELECT value FROM app_meta WHERE key='revision'").fetchone()
    payloads = [parse_json(row["payload"], {}) for row in db.execute("SELECT payload FROM capabilities ORDER BY rowid")]
    connection.close()
    return {
        "revision": int(rev_row["value"] if rev_row else 0),
        "data": payloads,
        "configData": config,
        "asOf": settings.get("asOf"),
        "source": f"sqlite:{path}",
    }


def load_state_from_api(url: str) -> dict:
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=20) as resp:
        state = json.loads(resp.read().decode("utf-8"))
    if not state.get("initialized") and not state.get("data"):
        raise RuntimeError("接口未初始化或没有数据")
    state["source"] = f"api:{url}"
    return state


def load_state_from_json(path: str) -> dict:
    state = json.loads(Path(path).read_text(encoding="utf-8"))
    state["source"] = f"json:{path}"
    return state


def auto_load(args) -> dict:
    if args.json:
        return load_state_from_json(args.json)
    if args.db:
        return load_state_from_db(args.db)
    if args.api:
        return load_state_from_api(args.api)
    try:
        return load_state_from_api(args.api_default)
    except (URLError, HTTPError, TimeoutError, RuntimeError, json.JSONDecodeError):
        pass
    candidates = [
        os.environ.get("MATURITY_DB_PATH"),
        r"E:\raft\V2.0.29\data\maturity.db",
        str(Path("data") / "maturity.db"),
        str(Path(__file__).resolve().parent / "maturity.db"),
    ]
    for path in candidates:
        if path and Path(path).is_file():
            return load_state_from_db(path)
    raise SystemExit("找不到数据。请指定 --api http://127.0.0.1:5000/api/state 或 --db 指向 maturity.db")


def domain_cat(domain: str) -> str:
    d = str(domain or "")
    if re.search(r"安规|合规|认证", d):
        return "合规"
    if re.search(r"可靠性|环境", d):
        return "环境可靠性"
    return d if d in CAPABILITY_DOMAINS else d


def achieved(row) -> bool:
    try:
        return int(row.get("achieved") or 0) == 1
    except (TypeError, ValueError):
        return False


def delivered(row) -> bool:
    return str(row.get("delivered") or "") == "已交付"


def planned_ok(row, month=FORECAST_MONTH) -> bool:
    try:
        pm = int(row.get("plannedMonth"))
    except (TypeError, ValueError):
        return False
    return 1 <= pm <= month


def forecast_hit(row) -> bool:
    return achieved(row) or (not achieved(row) and planned_ok(row))


def year_level(row) -> str:
    yd = (row.get("yearData") or {}).get("2026年") or {}
    return yd.get("level") or row.get("level") or ""


def cap_key(row) -> str:
    return "||".join(str(row.get(k) or "").strip() for k in ("domain", "owner", "dimension", "sub"))


def team_id_of(row, teams) -> str:
    raw = str(row.get("teamId") or "").strip()
    if raw and any(str(t.get("id")) == raw for t in teams):
        return raw
    name = str(row.get("team") or "").strip()
    for t in teams:
        if t.get("name") == name:
            return str(t.get("id"))
    return raw


def row_matches_team(row, team, teams) -> bool:
    want_id = str(team.get("id") or "")
    have_id = team_id_of(row, teams)
    if want_id and have_id:
        return str(have_id) == want_id
    return str(row.get("team") or "").strip() == str(team.get("name") or "")


def groups_of(rows):
    bucket = collections.OrderedDict()
    for row in rows:
        bucket.setdefault(cap_key(row), []).append(row)
    return [{"key": k, "items": v} for k, v in bucket.items()]


def active_teams(config):
    retired = {str(x) for x in (config.get("retiredTeamIds") or [])}
    retired_dept = {str(x) for x in (config.get("retiredDeptIds") or [])}
    teams = [t for t in (config.get("teams") or []) if str(t.get("id")) not in retired]
    depts = [d for d in (config.get("departments") or []) if str(d.get("id")) not in retired_dept]
    return teams, depts


def maturity_for_teams(team_objs, rows, teams_all, domain_limit=None, hit=achieved):
    if not team_objs:
        return None
    names = {t["name"] for t in team_objs}
    allowed = set(domain_limit) if domain_limit else None
    configured_domains = []
    for t in team_objs:
        for d in t.get("domains") or []:
            if d not in configured_domains:
                configured_domains.append(d)
    domains = [d for d in configured_domains if not allowed or d in allowed]
    grouped = groups_of(rows)
    domain_results = []
    for domain in domains:
        domain_teams = [t for t in team_objs if domain in (t.get("domains") or [])]
        domain_groups = [g for g in grouped if domain_cat(g["items"][0].get("domain")) == domain]
        levels = {}
        target_count = 0
        score = 0.0
        for level, weight in WEIGHTS.items():
            level_groups = [g for g in domain_groups if year_level(g["items"][0]) == level]
            total = len(level_groups) * len(domain_teams)
            got = 0
            for team in domain_teams:
                for g in level_groups:
                    if any(row_matches_team(item, team, teams_all) and hit(item) for item in g["items"]):
                        got += 1
            rate = (got / total) if total else None
            points = 0.0 if rate is None else rate * weight
            levels[level] = {"total": total, "achieved": got, "rate": rate, "points": points, "weight": weight}
            target_count += total
            score += points
        domain_results.append({"domain": domain, "score": score, "targetCount": target_count, "levels": levels})
    scorable = [x for x in domain_results if x["targetCount"] > 0]
    if not scorable:
        return None
    return sum(x["score"] for x in scorable) / len(scorable)


def avg_team_scores(team_objs, rows, teams_all, hit=achieved):
    parts = []
    for t in team_objs:
        s = maturity_for_teams([t], rows, teams_all, hit=hit)
        if s is not None:
            parts.append((t["name"], s))
    if not parts:
        return None
    return sum(s for _, s in parts) / len(parts)


def zpack(pairs):
    vals = [p for _, p in pairs]
    n = len(vals)
    if n < 2:
        return 0.0, 0.0, [(n_, p, 0.0, "低风险") for n_, p in pairs]
    mu = sum(vals) / n
    var = sum((x - mu) ** 2 for x in vals) / (n - 1)
    sigma = math.sqrt(var) if var > 0 else 0.0
    out = []
    for name, p in pairs:
        z = 0.0 if sigma == 0 else (p - mu) / sigma
        if z < -0.84:
            rk = "高风险"
        elif z < 0:
            rk = "中风险"
        else:
            rk = "低风险"
        out.append((name, p, z, rk))
    return mu, sigma, out


def esc(s):
    return htmlmod.escape("" if s is None else str(s)).replace("\r", " ").replace("\n", " ")


def clean(s):
    return " ".join(str(s or "").replace("\r", " ").replace("\n", " ").split())


def fmt(x, n=2):
    return f"{x:.{n}f}"


def heat_color(v):
    if v >= 3.0:
        return "#6a8f7a"
    if v >= 2.5:
        return "#b59a6a"
    return "#9a6b5a"


def mark_3(tc, tp):
    if tc >= 3.0:
        return '<span class="hit3">已达 3.0</span>'
    if tp >= 3.0:
        return '<span class="hit3 soon">预计 12 月达 3.0</span>'
    return ""


def pie_svg(pairs, size=140, center=""):
    total = sum(v for _, v in pairs) or 1
    cx = cy = size / 2
    r = size / 2 - 3
    inner = r * 0.58
    colors = ["#7a9e88", "#e8cfc6", "#c4b8a8", "#b7a07a", "#8aa89a", "#9a6b5a", "#cbb07a"]
    acc = 0.0
    paths = []

    def pt(frac):
        ang = -math.pi / 2 + frac * 2 * math.pi
        return cx + r * math.cos(ang), cy + r * math.sin(ang)

    for i, (_, val) in enumerate(pairs):
        if val <= 0:
            continue
        f0, f1 = acc / total, (acc + val) / total
        acc += val
        if f1 - f0 >= 0.999:
            paths.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{colors[i % len(colors)]}"/>')
            continue
        x0, y0 = pt(f0)
        x1, y1 = pt(f1)
        large = 1 if (f1 - f0) > 0.5 else 0
        paths.append(
            f'<path d="M{cx},{cy} L{x0:.1f},{y0:.1f} A{r},{r} 0 {large} 1 {x1:.1f},{y1:.1f} Z" fill="{colors[i % len(colors)]}"/>'
        )
    paths.append(f'<circle cx="{cx}" cy="{cy}" r="{inner:.1f}" fill="#fffcf7"/>')
    if center:
        paths.append(
            f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" font-size="{size * 0.18:.0f}" font-weight="650" fill="#3d3a37">{esc(center)}</text>'
        )
    return f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">{"".join(paths)}</svg>'


def roster(pairs, unit="项", hot=None):
    hot = hot or set()
    return (
        '<div class="roster">'
        + "".join(
            f'<div class="roster-item{" hot" if n in hot else ""}"><span class="roster-name">{esc(n)}</span>'
            f'<span class="roster-n">{int(v)}{unit}</span></div>'
            for n, v in pairs
        )
        + "</div>"
    )


def chips(pairs, unit="项"):
    return (
        '<div class="chip-wrap">'
        + "".join(f'<span class="chip">{esc(n)}　{int(v)}{unit}</span>' for n, v in pairs)
        + "</div>"
    )


def avg_line_bars(rows, avg, scale):
    width, label_w, row_h = 720, 200, 32
    h = 8 + row_h * len(rows)
    bar_w = width - label_w - 80
    ax = label_w + bar_w * (avg / scale)
    parts = [f'<svg viewBox="0 0 {width} {h}" width="100%" role="img">']
    parts.append(f'<line x1="{ax:.1f}" y1="4" x2="{ax:.1f}" y2="{h-4}" stroke="#a67c52" stroke-dasharray="4 3" stroke-width="1.2"/>')
    parts.append(f'<text x="{min(ax + 4, width - 80):.1f}" y="12" font-size="11" fill="#8a6a48">平均 {fmt(avg)}</text>')
    for i, (name, val, col) in enumerate(rows):
        y = 8 + i * row_h
        w = max(2, bar_w * (val / scale))
        parts.append(f'<text x="8" y="{y+12}" font-size="12" fill="#3d3a37">{esc(name)}</text>')
        parts.append(f'<rect x="{label_w}" y="{y}" width="{w:.1f}" height="16" rx="2" fill="{col}"/>')
        parts.append(f'<text x="{label_w + w + 6:.1f}" y="{y+12}" font-size="12" fill="#3d3a37">{fmt(val)}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


CSS = """
:root { --bg:#f4f1eb; --ink:#3d3a37; --muted:#6f6a64; --card:#fffcf7; --line:#e6dfd4; --accent:#5b7c6e; }
* { box-sizing:border-box; }
body { margin:0; font:15px/1.55 "PingFang SC","Noto Sans SC",sans-serif; color:var(--ink); background:var(--bg); }
.wrap { max-width:1080px; margin:0 auto; padding:28px 24px 64px; }
h1 { font-size:34px; font-weight:650; margin:0 0 10px; }
h2 { font-size:28px; margin:40px 0 14px; padding-top:10px; border-top:1px solid var(--line); }
h3 { font-size:22px; margin:26px 0 10px; color:var(--accent); }
.sub,.note { color:var(--muted); font-size:13px; }
.lead { margin:12px 0 8px; font-size:15px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; margin:10px 0 16px; }
.kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin:12px 0 18px; }
.kpi { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px; }
.kpi b { display:block; font-size:22px; font-weight:650; }
.kpi span { color:var(--muted); font-size:12px; }
.legend { display:flex; gap:14px; flex-wrap:wrap; margin:8px 0 14px; font-size:13px; }
.legend i { display:inline-block; width:12px; height:12px; border-radius:3px; margin-right:6px; vertical-align:-1px; }
.dept-block { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px 16px 10px; margin:14px 0 20px; }
.dept-head { display:flex; justify-content:flex-start; gap:18px; flex-wrap:wrap; align-items:baseline; margin-bottom:10px; }
.dept-name { font-size:20px; font-weight:650; }
.dept-head .rk { font-size:15px; padding:3px 10px; }
.dept-score { font-size:14px; color:var(--muted); }
.tile-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:10px; }
.tile { background:#f3efe7; border-radius:10px; padding:12px; }
.tile-name { font-size:13px; font-weight:600; min-height:2.4em; }
.tile-num { font-size:28px; font-weight:650; margin:4px 0; }
.tile-bar { height:6px; background:#e6dfd4; border-radius:99px; overflow:hidden; margin:6px 0; }
.tile-bar span { display:block; height:100%; background:#5b7c6e; }
.tile-sub { font-size:12px; color:var(--muted); margin-bottom:6px; }
.hit3 { display:inline-block; margin-left:8px; font-size:12px; font-weight:650; color:#2f5340; background:#d5e6db; border:1px solid #7a9e88; border-radius:999px; padding:1px 8px; }
.hit3.soon { color:#6e5728; background:#efe4c8; border-color:#cbb07a; }
.pills { display:flex; flex-wrap:wrap; gap:6px; }
.pill { background:#efeae2; border-radius:999px; padding:2px 8px; font-size:12px; color:var(--muted); }
table { width:100%; border-collapse:collapse; font-size:13px; margin-top:10px; }
th,td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); vertical-align:top; }
th { color:var(--ink); font-weight:700; }
.rk { font-size:12px; padding:2px 8px; border-radius:999px; font-weight:650; }
.低风险 { background:#d5e6db; color:#2f5340; border:1px solid #7a9e88; }
.中风险 { background:#efe4c8; color:#6e5728; border:1px solid #cbb07a; }
.高风险 { background:#e8cfc6; color:#6a3a30; border:1px solid #c4897a; }
.formula { font-family:ui-monospace,Menlo,monospace; font-size:13px; background:#efeae2; padding:12px 14px; border-radius:8px; white-space:pre-wrap; }
.roster { display:grid; grid-template-columns:repeat(auto-fill,minmax(160px,1fr)); gap:10px; }
.roster-item { background:#f3efe7; border-radius:10px; padding:12px 14px; display:flex; justify-content:space-between; align-items:baseline; gap:8px; }
.roster-name { font-size:15px; font-weight:600; }
.roster-n { font-size:26px; font-weight:650; }
.roster-item.hot { background:#f3d6d0; }
.roster-item.hot .roster-name, .roster-item.hot .roster-n { color:#9a3b32; }
.hot-name { color:#9a3b32; font-weight:650; }
.chip-wrap { display:flex; flex-wrap:wrap; gap:8px; }
.chip { background:#efeae2; border-radius:10px; padding:8px 10px; font-size:13px; line-height:1.4; max-width:100%; }
.heat-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }
.heat-cell { border-radius:12px; min-height:110px; padding:16px; color:#fffcf7; display:flex; flex-direction:column; justify-content:space-between; }
.heat-name { font-size:14px; }
.heat-num { font-size:36px; font-weight:650; }
.pie-with-legend { display:flex; gap:16px; align-items:center; flex-wrap:wrap; }
.owner-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.owner-grid > .card { margin:0; }
.cover-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.cover-grid > .card { margin:0; }
.toc { color:var(--muted); font-size:13px; margin:0 0 18px; }
.appendix { margin-top:48px; }
svg { display:block; overflow:visible; }
@media (max-width:900px){ .kpis,.owner-grid,.heat-grid,.cover-grid { grid-template-columns:1fr; } }
"""


def build_report(state: dict) -> dict:
    rows = state.get("data") or []
    config = state.get("configData") or {}
    teams_all, depts = active_teams(config)
    team_by_id = {str(t["id"]): t for t in teams_all}
    dept_teams = {}
    for d in depts:
        names = []
        for tid in d.get("teamIds") or []:
            t = team_by_id.get(str(tid))
            if t:
                names.append(t["name"])
        if names:
            dept_teams[d["name"]] = names
    team_cur, team_pred, team_dom_scores = {}, {}, {}
    for t in teams_all:
        cur = maturity_for_teams([t], rows, teams_all, hit=achieved)
        pred = maturity_for_teams([t], rows, teams_all, hit=forecast_hit)
        if cur is None:
            continue
        team_cur[t["name"]] = cur
        team_pred[t["name"]] = pred if pred is not None else cur
        ds = {}
        for d in t.get("domains") or []:
            s = maturity_for_teams([t], rows, teams_all, domain_limit=[d], hit=achieved)
            if s is not None:
                ds[d] = s
        team_dom_scores[t["name"]] = ds
    depts_out = []
    for dname, tnames in dept_teams.items():
        present = [n for n in tnames if n in team_cur]
        if not present:
            continue
        cur = sum(team_cur[n] for n in present) / len(present)
        pred = sum(team_pred[n] for n in present) / len(present)
        depts_out.append((dname, cur, pred, present))
    grouped = groups_of(rows)
    undelivered = []
    for g in grouped:
        if any(delivered(x) for x in g["items"]):
            continue
        x = g["items"][0]
        undelivered.append({
            "domain": domain_cat(x.get("domain")),
            "dimension": x.get("dimension") or "",
            "sub": x.get("sub") or "",
            "owner": x.get("owner") or "未填",
            "plannedMonth": x.get("plannedMonth"),
        })
    domain_team_names = collections.defaultdict(set)
    for t in teams_all:
        for d in t.get("domains") or []:
            if t["name"] in team_cur:
                domain_team_names[d].add(t["name"])
    low70 = []
    delivered_groups = [g for g in grouped if any(delivered(x) for x in g["items"])]
    for g in delivered_groups:
        dom = domain_cat(g["items"][0].get("domain"))
        related = [n for n in domain_team_names.get(dom, [])]
        if not related:
            continue
        got = 0
        for name in related:
            team = next((t for t in teams_all if t["name"] == name), None)
            if team and any(row_matches_team(item, team, teams_all) and achieved(item) for item in g["items"]):
                got += 1
        rate = got / len(related)
        if rate < 0.7:
            x = g["items"][0]
            low70.append({
                "domain": dom,
                "dimension": x.get("dimension") or "",
                "sub": x.get("sub") or "",
                "owner": x.get("owner") or "未填",
                "achievedTeams": got,
                "relatedTeams": len(related),
                "rate": rate,
            })
    plan = {10: [], 11: [], 12: []}
    for it in undelivered:
        try:
            m = int(it["plannedMonth"])
        except (TypeError, ValueError):
            continue
        if m in plan:
            plan[m].append(it)
    low5_detail = {}
    for name, score in sorted(team_cur.items(), key=lambda x: x[1])[:5]:
        team = next(t for t in teams_all if t["name"] == name)
        items = []
        for g in grouped:
            if not any(delivered(x) for x in g["items"]):
                continue
            if not any(row_matches_team(item, team, teams_all) for item in g["items"]) and domain_cat(g["items"][0].get("domain")) not in (team.get("domains") or []):
                continue
            if any(row_matches_team(item, team, teams_all) and achieved(item) for item in g["items"]):
                continue
            if domain_cat(g["items"][0].get("domain")) not in (team.get("domains") or []) and not any(row_matches_team(item, team, teams_all) for item in g["items"]):
                continue
            x = g["items"][0]
            items.append({"domain": domain_cat(x.get("domain")), "dimension": x.get("dimension") or "", "sub": x.get("sub") or ""})
        low5_detail[name] = items
    return {
        "state": state,
        "team_cur": team_cur,
        "team_pred": team_pred,
        "team_dom_scores": team_dom_scores,
        "depts": depts_out,
        "dept_teams": dept_teams,
        "undelivered": undelivered,
        "low70": low70,
        "plan": plan,
        "low5_detail": low5_detail,
        "teams_all": teams_all,
        "delivered_n": len(delivered_groups),
        "group_n": len(grouped),
    }


def render(report: dict, out_path: Path) -> None:
    team_cur = report["team_cur"]
    team_pred = report["team_pred"]
    depts = report["depts"]
    und = report["undelivered"]
    low70 = report["low70"]
    plan = report["plan"]
    state = report["state"]
    dept_cur_sorted = sorted(depts, key=lambda x: (-x[1], x[0]))
    mu_d, sd_d, dept_risk = zpack([(n, p) for n, c, p, ts in depts])
    mu_t, sd_t, team_risk = zpack([(n, team_pred[n]) for n in team_cur])
    dept_risk_map = {n: (rk, z, p) for n, p, z, rk in dept_risk}
    team_risk_map = {n: (rk, z, p) for n, p, z, rk in team_risk}
    center = sum(team_cur.values()) / len(team_cur) if team_cur else 0
    dept_avg = sum(c for _, c, _, _ in depts) / len(depts) if depts else 0
    domain_avg = {}
    for d in CAPABILITY_DOMAINS:
        vals = [team_cur[n] for n, ds in report["team_dom_scores"].items() if d in ds]
        if vals:
            domain_avg[d] = sum(vals) / len(vals)
    domain_sorted = sorted(domain_avg.items(), key=lambda x: -x[1])
    owner_rows = collections.Counter(x["owner"] for x in und).most_common()
    items_by_owner = collections.defaultdict(list)
    for it in und:
        items_by_owner[it["owner"]].append(it)
    hot = {n for n, _ in owner_rows[:3]}
    low70_by_dom = collections.OrderedDict()
    for it in sorted(low70, key=lambda x: (x["rate"], x["domain"], x["sub"])):
        low70_by_dom.setdefault(it["domain"], []).append(it)
    low5_names = [n for n, _ in sorted(team_cur.items(), key=lambda x: (x[1], x[0]))[:5]]
    n_high_d = sum(1 for *_, rk in dept_risk if rk == "高风险")
    n_high_t = sum(1 for *_, rk in team_risk if rk == "高风险")
    n_mid_d = sum(1 for *_, rk in dept_risk if rk == "中风险")
    n_low_d = sum(1 for *_, rk in dept_risk if rk == "低风险")
    n_mid_t = sum(1 for *_, rk in team_risk if rk == "中风险")
    n_low_t = sum(1 for *_, rk in team_risk if rk == "低风险")
    top2 = {dept_cur_sorted[0][0], dept_cur_sorted[1][0]} if len(dept_cur_sorted) >= 2 else set()
    bot2 = {dept_cur_sorted[-1][0], dept_cur_sorted[-2][0]} if len(dept_cur_sorted) >= 2 else set()
    scale_dept = max([3.0, dept_avg] + [c for _, c, _, _ in depts])
    dept_rows = []
    for name, cur, pred, ts in dept_cur_sorted:
        col = "#6a8f7a" if name in top2 else "#9a6b5a" if name in bot2 else "#5b7c6e"
        dept_rows.append((name, cur, col))

    def pills(team):
        ds = report["team_dom_scores"].get(team) or {}
        if len(ds) == 1:
            d, s = next(iter(ds.items()))
            return f'<span class="pill">{esc(d)} {fmt(s)}</span>'
        return "".join(f'<span class="pill">{esc(d)}</span>' for d in ds)

    team_html = []
    for name, cur, pred, tnames in dept_cur_sorted:
        rk, z, _ = dept_risk_map[name]
        tiles = []
        for team in sorted(tnames, key=lambda n: -team_cur.get(n, 0)):
            if team not in team_cur:
                continue
            tc, tp = team_cur[team], team_pred[team]
            trk, *_ = team_risk_map[team]
            pct = min(100, tc / 3.0 * 100)
            tiles.append(
                f'<div class="tile"><div class="tile-name">{esc(team)} {mark_3(tc, tp)}</div>'
                f'<div class="tile-num">{fmt(tc)}</div><div class="tile-bar"><span style="width:{pct:.1f}%"></span></div>'
                f'<div class="tile-sub">12月 {fmt(tp)}　<span class="rk {trk}">{trk}</span></div>'
                f'<div class="pills">{pills(team)}</div></div>'
            )
        team_html.append(
            f'<section class="dept-block"><div class="dept-head"><span class="dept-name">{esc(name)}</span>'
            f'<span class="dept-score">部门分 {fmt(cur)}　当前 {fmt(cur)} → 12月预测 {fmt(pred)}　'
            f'<span class="rk {rk}">{rk}</span></span></div><div class="tile-grid">{"".join(tiles)}</div></section>'
        )
    heat = "".join(
        f'<div class="heat-cell" style="background:{heat_color(v)}"><div class="heat-name">{esc(d)}</div>'
        f'<div class="heat-num">{fmt(v)}</div></div>'
        for d, v in domain_sorted
    )
    owner_detail = []
    for owner, n in owner_rows:
        its = items_by_owner[owner]
        by_dim = collections.Counter(it["dimension"] for it in its).most_common()
        by_cap = collections.Counter((it["dimension"], clean(it["sub"])) for it in its).most_common()
        cap_table = (
            "<table><thead><tr><th>评估维度</th><th>细分能力</th><th>项数</th></tr></thead><tbody>"
            + "".join(f"<tr><td>{esc(d)}</td><td>{esc(s)}</td><td>{v}</td></tr>" for (d, s), v in by_cap)
            + "</tbody></table>"
        )
        top_share = f"{int(round(100 * by_dim[0][1] / n))}%" if by_dim else ""
        owner_detail.append(
            f'<div class="card"><div class="dept-head"><span class="dept-name">{esc(owner)}</span>'
            f'<span class="dept-score">{n} 项</span></div><p class="lead">评估维度</p>'
            f'<div class="pie-with-legend">{pie_svg(by_dim, 140, top_share)}{chips(by_dim)}</div>'
            f'<p class="lead">能力项</p>{cap_table}</div>'
        )
    plan_html = []
    for month in (10, 11, 12):
        items = plan[month]
        own_rows = collections.Counter(it["owner"] for it in items).most_common()
        dim_rows = collections.Counter(it["dimension"] for it in items).most_common()
        plan_html.append(
            f'<div class="card"><div class="dept-head"><span class="dept-name">{month} 月</span>'
            f'<span class="dept-score">{len(items)} 项</span></div>'
            f'<p class="lead">按 Owner</p>{roster(own_rows)}'
            f'<p class="lead">按评估维度</p>{chips(dim_rows)}'
            f'<div class="chip-wrap" style="margin-top:10px">'
            + "".join(
                f'<span class="chip">{esc(it["domain"])} · {esc(it["dimension"])} · {esc(clean(it["sub"]))} · {esc(it["owner"])}</span>'
                for it in items
            )
            + "</div></div>"
        )
    low70_html = []
    for dom, its in low70_by_dom.items():
        tbl = "".join(
            f"<tr><td>{esc(it['sub'])}</td><td>{esc(it['dimension'])}</td><td>{esc(it['owner'])}</td>"
            f"<td>{it['achievedTeams']} / {it['relatedTeams']}</td>"
            f"<td class='hot-name'>{it['rate']*100:.1f}%</td></tr>"
            for it in its
        )
        low70_html.append(
            f'<div class="card"><div class="dept-head"><span class="dept-name">{esc(dom)}</span>'
            f'<span class="dept-score">{len(its)} 项</span></div>'
            f'<table><thead><tr><th>细分能力</th><th>评估维度</th><th>Owner</th>'
            f'<th>已达成科组 / 关联科组</th><th>达成率</th></tr></thead><tbody>{tbl}</tbody></table></div>'
        )
    low5_html = []
    for team in low5_names:
        items = report["low5_detail"].get(team) or []
        peer = ""
        for dname, tnames in report["dept_teams"].items():
            if team in tnames:
                others = [(n, team_cur[n]) for n in tnames if n != team and n in team_cur]
                others.sort(key=lambda x: -x[1])
                peer = others[0][0] if others else ""
                break
        block = [
            f'<div class="card"><div class="dept-head"><span class="dept-name">{esc(team)}</span>'
            f'<span class="dept-score">科组分 {fmt(team_cur[team])}</span></div>'
        ]
        if items:
            by_dom = collections.Counter(x["domain"] for x in items)
            by_dim = collections.Counter(f"{x['domain']} / {x['dimension']}" for x in items)
            block.append(f'<p class="lead">已交付但未达成 {len(items)} 项。建议向 {esc(peer)} 对齐。</p>')
            block.append(f'<p class="lead">按领域</p>{roster(by_dom.most_common())}')
            block.append(f'<p class="lead">按领域 / 评估维度</p>{chips(by_dim.most_common())}')
        else:
            block.append(f'<p class="lead">建议向同部门得分较高的 {esc(peer)} 对齐。没有已交付未达成明细则不编造。</p>')
        block.append("</div>")
        low5_html.append("".join(block))
    legend = (
        '<div class="legend"><span><i style="background:#e8cfc6;border:1px solid #c4897a"></i>高风险</span>'
        '<span><i style="background:#efe4c8;border:1px solid #cbb07a"></i>中风险</span>'
        '<span><i style="background:#d5e6db;border:1px solid #7a9e88"></i>低风险</span></div>'
    )
    heat_legend = (
        '<div class="legend"><span><i style="background:#6a8f7a"></i>≥ 3.0</span>'
        '<span><i style="background:#b59a6a"></i>2.5 – 3.0</span>'
        '<span><i style="background:#9a6b5a"></i>&lt; 2.5</span></div>'
    )
    src = state.get("source") or ""
    rev = state.get("revision")
    generated = date.today().isoformat()
    data_asof = state.get("asOf") or generated
    und_n, grp_n = len(und), report["group_n"]
    share = und_n / grp_n if grp_n else 0
    top2_txt = f"{dept_cur_sorted[0][0]}（{fmt(dept_cur_sorted[0][1])}）" + (f"、{dept_cur_sorted[1][0]}（{fmt(dept_cur_sorted[1][1])}）" if len(dept_cur_sorted) >= 2 else "")
    bot2_txt = f"{dept_cur_sorted[-1][0]}（{fmt(dept_cur_sorted[-1][1])}）" + (f"、{dept_cur_sorted[-2][0]}（{fmt(dept_cur_sorted[-2][1])}）" if len(dept_cur_sorted) >= 2 else "")
    low_depts = [(n, c) for n, c, _, _ in depts if c < 2.5]
    low_teams = sorted(((n, s) for n, s in team_cur.items() if s < 2.5), key=lambda x: x[1])
    cover_dept_rows = "".join(
        f"<tr><td>{esc(n)}</td><td>{fmt(c)}</td><td>{'最高' if n in top2 else '最低'}</td></tr>"
        for n, c, _, _ in ([dept_cur_sorted[0], dept_cur_sorted[1]] if len(dept_cur_sorted) >= 2 else dept_cur_sorted)
        + ([dept_cur_sorted[-2], dept_cur_sorted[-1]] if len(dept_cur_sorted) >= 2 else [])
    )
    cover_low5_rows = "".join(
        f"<tr><td>{esc(n)}</td><td>{fmt(team_cur[n])}</td><td>{fmt(team_pred[n])}</td></tr>"
        for n in low5_names
    )
    low_dept_rows = "".join(f"<tr><td>{esc(n)}</td><td class='hot-name'>{fmt(c)}</td></tr>" for n, c in low_depts) or "<tr><td colspan='2'>没有低于 2.5 的部门</td></tr>"
    low_team_rows = "".join(f"<tr><td>{esc(n)}</td><td class='hot-name'>{fmt(s)}</td></tr>" for n, s in low_teams) or "<tr><td colspan='2'>没有低于 2.5 的科组</td></tr>"
    und_table = "".join(
        f"<tr><td>{esc(it['domain'])}</td><td>{esc(it['dimension'])}</td><td>{esc(it['sub'])}</td>"
        f"<td class='{'hot-name' if it['owner'] in hot else ''}'>{esc(it['owner'])}</td>"
        f"<td>{esc(it['plannedMonth'])}</td></tr>"
        for it in und
    )
    team_appendix_rows = []
    for dname, cur, pred, tnames in dept_cur_sorted:
        for team in sorted(tnames, key=lambda n: -team_cur.get(n, 0)):
            if team not in team_cur:
                continue
            team_appendix_rows.append(
                f"<tr><td>{esc(dname)}</td><td>{esc(team)}</td><td>{fmt(team_cur[team])}</td><td>{fmt(team_pred[team])}</td></tr>"
            )
    html_out = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>测试能力成熟度月报</title><style>{CSS}</style></head><body><div class="wrap">
<h1>测试能力成熟度月报</h1>
<p class="sub">生成日 {generated}　数据 {esc(src)}　revision {esc(rev)}　库 asOf {esc(data_asof)}　科组=关联领域得分平均；部门=科组等权平均。无 8–12 月历史，趋势仅当前→12月预测。</p>
<p class="toc">封面结论 → 重点异常 → 附录明细</p>
<div class="kpis">
  <div class="kpi"><b>{fmt(center)}</b><span>全中心综合得分（科组等权）</span></div>
  <div class="kpi"><b>{fmt(dept_avg)}</b><span>部门平均得分</span></div>
  <div class="kpi"><b>{und_n}/{grp_n}</b><span>未交付能力项及占比 {share*100:.1f}%</span></div>
  <div class="kpi"><b>{len(low70)}</b><span>已交付能力达成率低于 70%</span></div>
</div>
<div class="cover-grid">
  <div class="card"><p class="lead">部门最高 / 最低各两项</p>
  <table><thead><tr><th>部门</th><th>当前分</th><th></th></tr></thead><tbody>{cover_dept_rows}</tbody></table></div>
  <div class="card"><p class="lead">未交付 Owner 前三</p>{roster(owner_rows[:3], hot=hot)}</div>
</div>
<div class="card"><p class="lead">得分后五名科组</p>
<table><thead><tr><th>科组</th><th>当前</th><th>12月预测</th></tr></thead><tbody>{cover_low5_rows}</tbody></table></div>
<p class="note">最高部门 {top2_txt}；最低部门 {bot2_txt}。</p>

<h2>重点异常</h2>
<p class="lead">只列低于 2.5、未交付、达成率不到 70%。正常项不展开。</p>
<div class="cover-grid">
  <div class="card"><p class="lead">部门当前分低于 2.5</p>
  <table><thead><tr><th>部门</th><th>当前分</th></tr></thead><tbody>{low_dept_rows}</tbody></table></div>
  <div class="card"><p class="lead">科组当前分低于 2.5</p>
  <table><thead><tr><th>科组</th><th>当前分</th></tr></thead><tbody>{low_team_rows}</tbody></table></div>
</div>
<div class="card">{heat_legend}<div class="heat-grid">{heat}</div></div>
<div class="card"><p class="lead">未交付 {und_n} 项。Owner 前三已标红。</p>
<table><thead><tr><th>领域</th><th>评估维度</th><th>细分能力</th><th>Owner</th><th>预计月</th></tr></thead><tbody>{und_table}</tbody></table></div>
<p class="lead">已交付 {report['delivered_n']} 项中，{len(low70)} 项达成率低于 70%。</p>
{''.join(low70_html)}

<div class="appendix">
<h2>附录</h2>
<p class="lead">36 个科组全表、Owner 明细。需要时再翻。</p>
<div class="card"><p class="lead">科组全表</p>
<table><thead><tr><th>部门</th><th>科组</th><th>当前</th><th>12月预测</th></tr></thead><tbody>{''.join(team_appendix_rows)}</tbody></table></div>
<div class="owner-grid">{''.join(owner_detail)}</div>
</div>
<p class="note">单文件 HTML，双击打开。脚本只读数据，未写库。</p>
</div></body></html>
"""
    out_path.write_text(html_out, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="生成测试能力成熟度月报 HTML")
    parser.add_argument("--api", help="5000 状态接口，例如 http://127.0.0.1:5000/api/state")
    parser.add_argument("--api-default", default="http://127.0.0.1:5000/api/state")
    parser.add_argument("--db", help="maturity.db 路径")
    parser.add_argument("--json", help="state JSON 路径")
    parser.add_argument("--out", default="", help="输出 HTML 路径")
    args = parser.parse_args()
    state = auto_load(args)
    report = build_report(state)
    out = Path(args.out) if args.out else Path.cwd() / f"测试能力成熟度月报-{date.today().isoformat()}.html"
    render(report, out)
    print(f"OK {out}")
    print(f"source={state.get('source')} revision={state.get('revision')} teams={len(report['team_cur'])} depts={len(report['depts'])} undelivered={len(report['undelivered'])} low70={len(report['low70'])}")


if __name__ == "__main__":
    main()
