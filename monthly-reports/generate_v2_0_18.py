# -*- coding: utf-8 -*-
"""测试能力成熟度月报生成器（Python 3.10+）。

从本地 SQLite 只读计算七章 HTML。达成率与得分一律来自传入库，不编造。
质量结果等无真实来源的「各类基准指标」才允许假数据，并显著标记「临时演示」。

用法（落地机）：
  py -3.10 generate_v2_0_18.py --db "E:\\raft\\V2.0.18\\source\\data\\maturity.db"
  py -3.10 generate_v2_0_18.py --db "<当前 5000 正式库路径>" --out-dir "E:\\raft\\monthly-reports\\v2.0.18"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import statistics
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

REPORT_VER = "V2.0.18"
TARGET_SCORE = 3.0
FULL_SCORE = 4.0
SCORE_WEIGHTS = {"2级": 2.0, "3级": 1.0, "4级": 1.0}
CAPABILITY_DOMAINS = ["软件", "硬件", "机械", "EMC", "合规", "环境可靠性"]
PLAN_MONTHS = (9, 10, 11, 12)

DEFAULT_DB_CANDIDATES = [
    Path(r"E:\raft\V2.0.18\source\data\maturity.db"),
    Path(r"E:\raft\V2.0.17\source\data\maturity.db"),
    Path(r"E:\raft\V2.0.16\source\data\maturity.db"),
    Path(r"E:\raft\V2.0.15\source\data\maturity.db"),
]


def esc(v):
    return (
        str(v if v is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def is_achieved(item):
    v = item.get("achieved")
    return v in (1, True, "1", "true", "True")


def domain_category(name):
    text = str(name or "").strip()
    if not text:
        return ""
    if any(k in text for k in ("安规", "合规", "认证")):
        return "合规"
    if any(k in text for k in ("可靠性", "环境")):
        return "环境可靠性"
    if text in CAPABILITY_DOMAINS:
        return text
    return text


def cap_key(item):
    return "||".join(
        str(item.get(k) or "").strip() for k in ("domain", "owner", "dimension", "sub")
    )


def parse_json(text, fallback):
    if not text:
        return fallback
    try:
        return json.loads(text)
    except Exception:
        return fallback


def parse_month(value):
    if value in (None, "", 0, "0"):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        m = int(value)
        return m if 1 <= m <= 12 else None
    s = str(value).strip()
    if not s:
        return None
    if s.isdigit():
        m = int(s)
        return m if 1 <= m <= 12 else None
    for fmt in ("%Y-%m", "%Y/%m", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[: len(fmt.replace("%Y", "2026"))], fmt).month
        except Exception:
            continue
    digits = "".join(ch for ch in s if ch.isdigit())
    if len(digits) >= 6:
        m = int(digits[4:6])
        return m if 1 <= m <= 12 else None
    return None


def item_plan_month(item):
    for key in (
        "plannedMonth",
        "planned_month",
        "planMonth",
        "expectedMonth",
        "预计达成时间",
        "预计达成月份",
    ):
        m = parse_month(item.get(key))
        if m:
            return m
    return None


def fmt_score(v, digits=2):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    return f"{v:.{digits}f}"


def fmt_pct(v):
    if v is None:
        return "—"
    return f"{v:.1f}%"


def avg(values):
    vals = [v for v in values if v is not None]
    return (sum(vals) / len(vals)) if vals else None


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def table_names(cur):
    return {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def table_columns(cur, name):
    return [r[1] for r in cur.execute("PRAGMA table_info(%s)" % name)]


def resolve_db(cli_path):
    if cli_path:
        p = Path(cli_path)
        if not p.is_file():
            raise SystemExit("数据库不存在：%s" % p)
        return p.resolve()
    for cand in DEFAULT_DB_CANDIDATES:
        if cand.is_file():
            return cand.resolve()
    raise SystemExit(
        "未找到正式库。请用 --db 传入当前 5000 正在使用的 maturity.db（V2.0.18 切过去就传 18 的路径）。"
    )


def resolve_out_dir(cli_path):
    if cli_path:
        p = Path(cli_path)
        p.mkdir(parents=True, exist_ok=True)
        return p.resolve()
    land = Path(r"E:\raft\monthly-reports")
    if land.exists() or Path(r"E:\raft").exists():
        p = land / "v2.0.18"
        p.mkdir(parents=True, exist_ok=True)
        return p.resolve()
    p = Path(__file__).resolve().parent / "v2.0.18"
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_db(db_path):
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    names = table_names(cur)
    meta = {}
    if "app_meta" in names:
        meta.update({r[0]: r[1] for r in cur.execute("SELECT key, value FROM app_meta")})
    if "app_settings" in names:
        meta.update(
            {"setting:" + r[0]: r[1] for r in cur.execute("SELECT key, value FROM app_settings")}
        )

    items = []
    for row in cur.execute("SELECT id, payload FROM capabilities"):
        payload = parse_json(row["payload"], {})
        if not isinstance(payload, dict):
            continue
        payload["_id"] = row["id"]
        payload["domain_cat"] = domain_category(payload.get("domain"))
        items.append(payload)

    teams = []
    if "teams" in names:
        cols = set(table_columns(cur, "teams"))
        for row in cur.execute("SELECT * FROM teams"):
            domains = parse_json(row["domains"], []) if "domains" in cols else []
            if not isinstance(domains, list):
                domains = []
            teams.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "domains": [domain_category(d) for d in domains if d],
                }
            )

    org_units = []
    if "org_units" in names:
        for row in cur.execute("SELECT id, kind, name FROM org_units"):
            org_units.append({"id": row["id"], "kind": row["kind"], "name": row["name"]})

    relations = defaultdict(list)
    if "org_team_relations" in names:
        for org_id, team_id in cur.execute("SELECT org_id, team_id FROM org_team_relations"):
            relations[org_id].append(team_id)

    change_logs = []
    if "change_logs" in names:
        cols = table_columns(cur, "change_logs")
        payload_col = "payload" if "payload" in cols else cols[-1]
        for row in cur.execute("SELECT * FROM change_logs"):
            change_logs.append(parse_json(row[payload_col], {"raw": row[payload_col]}))

    gap_notes = []
    if "monthly_gap_notes" in names:
        cols = table_columns(cur, "monthly_gap_notes")
        for row in cur.execute("SELECT * FROM monthly_gap_notes"):
            gap_notes.append({c: row[c] for c in cols})

    conn.close()
    return {
        "items": items,
        "teams": teams,
        "org_units": org_units,
        "relations": relations,
        "change_logs": change_logs,
        "gap_notes": gap_notes,
        "meta": meta,
    }


def infer_team_domains(teams, items):
    by_team = defaultdict(set)
    for it in items:
        if it.get("team") and it.get("domain_cat"):
            by_team[it["team"]].add(it["domain_cat"])
    for team in teams:
        if not team["domains"]:
            team["domains"] = sorted(by_team.get(team["name"], []))
    known = {t["name"] for t in teams}
    for name, domains in by_team.items():
        if name not in known:
            teams.append(
                {
                    "id": "inferred-%s" % name,
                    "name": name,
                    "domains": sorted(domains),
                }
            )
    return teams


def build_groups(items):
    groups = {}
    for it in items:
        key = cap_key(it)
        if key not in groups:
            groups[key] = {"key": key, "items": []}
        groups[key]["items"].append(it)
    return list(groups.values())


def team_domain_score(team, domain, groups):
    """科组-领域得分 = 2级达成率×2 + 3级达成率 + 4级达成率（5级不计）。"""
    domain_groups = [
        g
        for g in groups
        if domain_category(g["items"][0].get("domain")) == domain
    ]
    levels = {}
    target_count = 0
    for level, weight in SCORE_WEIGHTS.items():
        level_groups = [
            g
            for g in domain_groups
            if str(g["items"][0].get("level") or "") == level
        ]
        total = len(level_groups)
        achieved_n = sum(
            1
            for g in level_groups
            if any(x.get("team") == team["name"] and is_achieved(x) for x in g["items"])
        )
        rate = (achieved_n / total) if total else None
        points = 0.0 if rate is None else rate * weight
        levels[level] = {
            "level": level,
            "weight": weight,
            "total": total,
            "achieved": achieved_n,
            "rate": rate,
            "points": points,
        }
        target_count += total
    score = sum(v["points"] for v in levels.values()) if target_count else None
    return {"score": score, "levels": levels, "targetCount": target_count}


def team_score_result(team, groups):
    domain_results = []
    for domain in team["domains"]:
        if domain not in CAPABILITY_DOMAINS and domain not in {
            domain_category(g["items"][0].get("domain")) for g in groups
        }:
            continue
        result = team_domain_score(team, domain, groups)
        result["domain"] = domain
        domain_results.append(result)
    scorable = [d for d in domain_results if d["targetCount"] > 0 and d["score"] is not None]
    score = avg([d["score"] for d in scorable])
    return {"score": score, "domains": domain_results, "scorable": scorable}


def org_equal_weight(team_results, team_ids):
    scores = [
        team_results[tid]["score"]
        for tid in team_ids
        if tid in team_results and team_results[tid]["score"] is not None
    ]
    return avg(scores)


def item_stats(items):
    n = len(items)
    done = sum(1 for x in items if is_achieved(x))
    return {"n": n, "done": done, "gap": n - done, "rate": (done / n * 100.0) if n else None}


def predicted_items(items, through_month):
    out = []
    for it in items:
        clone = dict(it)
        if not is_achieved(clone):
            pm = item_plan_month(clone)
            if pm is not None and pm <= through_month:
                clone["achieved"] = 1
        out.append(clone)
    return out


def band_label(score, ordered_scores):
    if score is None or not ordered_scores:
        return ("na", "暂无")
    n = len(ordered_scores)
    band = max(1, math.ceil(n * 0.1))
    eps = 1e-9
    if n > 1 and score >= ordered_scores[0] - eps and score >= ordered_scores[min(band, n) - 1] - eps:
        return ("leading", "领先（前 10%）")
    if n > 1 and score <= ordered_scores[-1] + eps and score <= ordered_scores[-min(band, n)] + eps:
        return ("base", "基础（后 10%）")
    if score >= TARGET_SCORE:
        return ("ok", "达标")
    if score >= 2.0:
        return ("dev", "发展")
    return ("base", "基础")


def heat_class(score):
    if score is None:
        return "h-na"
    if score >= TARGET_SCORE:
        return "h-good"
    if score >= 2.0:
        return "h-mid"
    if score >= 1.0:
        return "h-low"
    return "h-bad"


def risk_conclusion(current, predicted_dec, plan_cover, gap_n):
    if current is None:
        return "当前范围没有可计分科组，无法给出年度目标风险评估。"
    gap = TARGET_SCORE - current
    if current >= TARGET_SCORE:
        return "当前全中心得分已达到年度目标 3.0。后续重点是巩固短板、避免已达成项回退。"
    if predicted_dec is not None and predicted_dec >= TARGET_SCORE:
        return (
            "当前得分 %.2f，距目标差 %.2f。按已标记计划月份把 9–12 月计划项视为达成后，"
            "预测年底得分 %.2f，规则上可覆盖年度目标；前提是计划按期兑现。"
            % (current, gap, predicted_dec)
        )
    if plan_cover < 0.3 and gap_n:
        return (
            "当前得分 %.2f，距目标差 %.2f；未达成 %d 项中计划月份覆盖偏低（%.0f%%）。"
            "规则结论：年度目标 3.0 风险高，需尽快补齐 9–12 月计划。"
            % (current, gap, gap_n, plan_cover * 100)
        )
    return (
        "当前得分 %.2f，距目标差 %.2f。按现有计划月份预测年底仍可能低于 3.0。"
        "规则结论：存在年度目标缺口，优先压实高权重未达成项（2 级）的计划。"
        % (current, gap)
    )


def demo_quality_block():
    return """
<section class="panel demo-panel">
  <div class="sec-title">4.5 测试质量结果指标 <span class="tag t-demo">临时演示 · 后续用真实数据替换</span></div>
  <p class="warn">本小节<strong>不是</strong>成熟度库数据。当前库中没有平均缺陷数、reopen 率等质量结果字段，以下数字仅为版式占位，禁止当正式结论引用。</p>
  <div class="grid3">
    <div class="card demo-card">平均缺陷数 / 产品<span class="tag t-demo">临时演示</span><b>3.2</b><span class="muted">占位 · 非正式</span></div>
    <div class="card demo-card">平均 reopen 率<span class="tag t-demo">临时演示</span><b>8.5%</b><span class="muted">占位 · 非正式</span></div>
    <div class="card demo-card">行业对照（无来源）<span class="tag t-demo">临时演示</span><b>不引用</b><span class="muted">不使用来源不明的网上数据</span></div>
  </div>
</section>
"""


def bar_rows(pairs, max_score=4.0):
    html = []
    for name, score in pairs:
        width = 0 if score is None else min(100.0, score / max_score * 100.0)
        html.append(
            '<div class="chart-row"><span>%s</span><i style="width:%.0f%%"></i><b>%s</b></div>'
            % (esc(name), width, fmt_score(score))
        )
    return "".join(html)


def table_html(headers, rows):
    th = "".join("<th>%s</th>" % esc(h) for h in headers)
    body = []
    for row in rows:
        tds = []
        for i, cell in enumerate(row):
            cls = ' class="score"' if i == 1 else ""
            tds.append("<td%s>%s</td>" % (cls, cell))
        body.append("<tr>%s</tr>" % "".join(tds))
    if not body:
        body.append('<tr><td colspan="%d" class="muted">当前库没有可展示记录</td></tr>' % len(headers))
    return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (th, "".join(body))


def compute(data, period):
    items = data["items"]
    teams = infer_team_domains(list(data["teams"]), items)
    groups = build_groups(items)
    team_by_id = {t["id"]: t for t in teams}
    team_by_name = {t["name"]: t for t in teams}

    team_results = {}
    for team in teams:
        team_results[team["id"]] = team_score_result(team, groups)

    depts = [u for u in data["org_units"] if u["kind"] in ("department", "dept")]
    businesses = [u for u in data["org_units"] if u["kind"] in ("business", "biz")]

    dept_rows = []
    for org in depts:
        tids = data["relations"].get(org["id"], [])
        names = [team_by_id[t]["name"] for t in tids if t in team_by_id]
        linked_items = [x for x in items if x.get("team") in names]
        st = item_stats(linked_items)
        score = org_equal_weight(team_results, tids)
        dept_rows.append(
            {
                "id": org["id"],
                "name": org["name"],
                "score": score,
                "teams": names,
                "n": st["n"],
                "done": st["done"],
                "rate": st["rate"],
                "gap_n": st["gap"],
            }
        )

    biz_rows = []
    for org in businesses:
        tids = data["relations"].get(org["id"], [])
        names = [team_by_id[t]["name"] for t in tids if t in team_by_id]
        linked_items = [x for x in items if x.get("team") in names]
        st = item_stats(linked_items)
        score = org_equal_weight(team_results, tids)
        biz_rows.append(
            {
                "id": org["id"],
                "name": org["name"],
                "score": score,
                "teams": names,
                "n": st["n"],
                "done": st["done"],
                "rate": st["rate"],
                "gap_n": st["gap"],
            }
        )

    team_rows = []
    for team in teams:
        nameset = team["name"]
        linked_items = [x for x in items if x.get("team") == nameset]
        st = item_stats(linked_items)
        tr = team_results[team["id"]]
        team_rows.append(
            {
                "id": team["id"],
                "name": team["name"],
                "domains": team["domains"],
                "score": tr["score"],
                "domain_scores": {d["domain"]: d["score"] for d in tr["domains"]},
                "n": st["n"],
                "done": st["done"],
                "rate": st["rate"],
                "gap_n": st["gap"],
            }
        )

    overall_score = avg([r["score"] for r in team_rows])
    overall_items = item_stats(items)

    domain_rows = []
    for domain in CAPABILITY_DOMAINS:
        scores = [
            r["domain_scores"].get(domain)
            for r in team_rows
            if domain in (r["domains"] or [])
        ]
        d_items = [x for x in items if x.get("domain_cat") == domain]
        st = item_stats(d_items)
        domain_rows.append(
            {
                "name": domain,
                "score": avg(scores),
                "n": st["n"],
                "done": st["done"],
                "rate": st["rate"],
                "gap_n": st["gap"],
            }
        )
    extra_domains = sorted(
        {
            x.get("domain_cat")
            for x in items
            if x.get("domain_cat") and x.get("domain_cat") not in CAPABILITY_DOMAINS
        }
    )
    for domain in extra_domains:
        d_items = [x for x in items if x.get("domain_cat") == domain]
        st = item_stats(d_items)
        domain_rows.append(
            {
                "name": domain + "（未归入六大领域）",
                "score": None,
                "n": st["n"],
                "done": st["done"],
                "rate": st["rate"],
                "gap_n": st["gap"],
            }
        )

    dim_map = defaultdict(list)
    for x in items:
        dim_map[str(x.get("dimension") or "未标注")].append(x)
    dim_rows = []
    for name, rows in sorted(dim_map.items()):
        st = item_stats(rows)
        dim_rows.append({"name": name, "n": st["n"], "done": st["done"], "rate": st["rate"]})

    ordered_team_scores = sorted(
        [r["score"] for r in team_rows if r["score"] is not None], reverse=True
    )
    for r in team_rows:
        key, label = band_label(r["score"], ordered_team_scores)
        r["band"] = label
        r["band_key"] = key

    plan_dist = {m: 0 for m in PLAN_MONTHS}
    unmarked = 0
    planned_unmet = []
    for x in items:
        if is_achieved(x):
            continue
        m = item_plan_month(x)
        if m is None:
            unmarked += 1
        else:
            if m in plan_dist:
                plan_dist[m] += 1
            planned_unmet.append((m, x))

    pred_by_month = {}
    for m in PLAN_MONTHS:
        pred_items = predicted_items(items, m)
        pred_groups = build_groups(pred_items)
        pred_scores = []
        for team in teams:
            pred_scores.append(team_score_result(team, pred_groups)["score"])
        pred_by_month[m] = avg(pred_scores)

    unmet = [x for x in items if not is_achieved(x)]
    plan_cover = (len(unmet) - unmarked) / len(unmet) if unmet else 1.0

    new_achieved = []
    year, month = [int(x) for x in period.split("-")]
    for log in data["change_logs"]:
        if not isinstance(log, dict):
            continue
        text = json.dumps(log, ensure_ascii=False)
        time_s = str(log.get("time") or log.get("created_at") or log.get("at") or "")
        keep = False
        if time_s.startswith("%04d-%02d" % (year, month)):
            keep = True
        if any(k in text for k in ("达成", "achieved", "attain")):
            keep = True if time_s[:7] == period or not time_s else keep
        if keep and ("达成" in text or "achieved" in text):
            new_achieved.append(log)

    notes_summary = []
    for note in data["gap_notes"]:
        blob = " ".join(str(v) for v in note.values() if v not in (None, ""))
        if blob.strip():
            notes_summary.append(note)

    return {
        "items": items,
        "teams": teams,
        "groups": groups,
        "team_rows": sorted(
            team_rows, key=lambda r: (-(r["score"] if r["score"] is not None else -1), r["name"])
        ),
        "dept_rows": sorted(
            dept_rows, key=lambda r: (-(r["score"] if r["score"] is not None else -1), r["name"])
        ),
        "biz_rows": sorted(
            biz_rows, key=lambda r: (-(r["score"] if r["score"] is not None else -1), r["name"])
        ),
        "domain_rows": domain_rows,
        "dim_rows": dim_rows,
        "overall_score": overall_score,
        "overall_items": overall_items,
        "plan_dist": plan_dist,
        "unmarked": unmarked,
        "pred_by_month": pred_by_month,
        "plan_cover": plan_cover,
        "unmet": unmet,
        "new_achieved": new_achieved,
        "notes_summary": notes_summary,
        "team_by_name": team_by_name,
    }


def snapshot_payload(ctx, meta):
    return {
        "period": meta["period"],
        "generated_at": meta["generated_at"],
        "db_path": meta["db_path"],
        "db_sha256": meta["db_sha256"],
        "n_items": ctx["overall_items"]["n"],
        "n_done": ctx["overall_items"]["done"],
        "attain_rate": ctx["overall_items"]["rate"],
        "center_score": ctx["overall_score"],
        "domains": [
            {"name": r["name"], "score": r["score"], "rate": r["rate"], "n": r["n"]}
            for r in ctx["domain_rows"]
        ],
        "teams": [
            {"name": r["name"], "score": r["score"], "rate": r["rate"], "n": r["n"]}
            for r in ctx["team_rows"]
        ],
        "departments": [
            {"name": r["name"], "score": r["score"], "rate": r["rate"], "n": r["n"]}
            for r in ctx["dept_rows"]
        ],
        "businesses": [
            {"name": r["name"], "score": r["score"], "rate": r["rate"], "n": r["n"]}
            for r in ctx["biz_rows"]
        ],
    }


def render_html(ctx, meta):
    oi = ctx["overall_items"]
    overall = ctx["overall_score"]
    gap = None if overall is None else overall - TARGET_SCORE
    valid_domains = [d for d in ctx["domain_rows"] if d["score"] is not None]
    best_d = max(valid_domains, key=lambda x: x["score"]) if valid_domains else None
    weak_d = min(valid_domains, key=lambda x: x["score"]) if valid_domains else None
    valid_teams = [t for t in ctx["team_rows"] if t["score"] is not None]
    best_t = valid_teams[0] if valid_teams else None
    weak_t = valid_teams[-1] if valid_teams else None
    valid_depts = [d for d in ctx["dept_rows"] if d["score"] is not None]
    best_dept = valid_depts[0] if valid_depts else None
    weak_dept = valid_depts[-1] if valid_depts else None
    valid_biz = [d for d in ctx["biz_rows"] if d["score"] is not None]
    best_biz = valid_biz[0] if valid_biz else None
    weak_biz = valid_biz[-1] if valid_biz else None

    lagging = [t for t in ctx["team_rows"] if t.get("band_key") == "base"]
    leading = [t for t in ctx["team_rows"] if t.get("band_key") == "leading"]

    if overall is None:
        overall_note = "当前没有可按 V2.0.18 口径计分的科组。"
    elif overall < TARGET_SCORE:
        overall_note = (
            "当前全中心得分为 %s（科组等权平均），较年度目标 3.0 低 %s 分，能力项达成率 %s；"
            "未达成 %d 项。建议优先处理低分领域和后 10%% 科组。"
            % (
                fmt_score(overall),
                fmt_score(TARGET_SCORE - overall),
                fmt_pct(oi["rate"]),
                oi["gap"],
            )
        )
    else:
        overall_note = (
            "当前全中心得分 %s，已达到年度目标 3.0，达成率 %s。后续转向巩固短板。"
            % (fmt_score(overall), fmt_pct(oi["rate"]))
        )

    if ctx["new_achieved"]:
        change_note = "本期修改记录中识别到 %d 条与达成相关的记录（见清单）。" % len(ctx["new_achieved"])
    elif ctx["change_logs"] if False else not ctx["new_achieved"]:
        change_note = (
            "当前库 change_logs 未提供可解析的本月新增达成清单，故不虚构趋势。"
            "历史月度对比待快照积累后启用。"
        )
    else:
        change_note = "无本期新增达成记录。"

    pred_dec = ctx["pred_by_month"].get(12)
    risk_text = risk_conclusion(overall, pred_dec, ctx["plan_cover"], oi["gap"])

    pie = 0.0 if oi["rate"] is None else oi["rate"]
    domain_bars = bar_rows([(d["name"], d["score"]) for d in ctx["domain_rows"] if "未归入" not in d["name"]])

    team_table = table_html(
        ["科组", "得分", "达成率", "能力项", "未达成", "分档", "距 3.0"],
        [
            [
                esc(r["name"]),
                fmt_score(r["score"]),
                fmt_pct(r["rate"]),
                str(r["n"]),
                str(r["gap_n"]),
                esc(r["band"]),
                "—" if r["score"] is None else fmt_score(r["score"] - TARGET_SCORE),
            ]
            for r in ctx["team_rows"]
        ],
    )
    dept_table = table_html(
        ["部门", "得分（科组等权）", "达成率", "能力项", "关联科组", "距 3.0"],
        [
            [
                esc(r["name"]),
                fmt_score(r["score"]),
                fmt_pct(r["rate"]),
                str(r["n"]),
                str(len(r["teams"])),
                "—" if r["score"] is None else fmt_score(r["score"] - TARGET_SCORE),
            ]
            for r in ctx["dept_rows"]
        ],
    )
    biz_table = table_html(
        ["业务线", "得分（科组等权）", "达成率", "能力项", "关联科组", "距 3.0"],
        [
            [
                esc(r["name"]),
                fmt_score(r["score"]),
                fmt_pct(r["rate"]),
                str(r["n"]),
                str(len(r["teams"])),
                "—" if r["score"] is None else fmt_score(r["score"] - TARGET_SCORE),
            ]
            for r in ctx["biz_rows"]
        ],
    )
    domain_table = table_html(
        ["领域", "得分（关联科组等权）", "达成率", "能力项", "未达成", "距 3.0"],
        [
            [
                esc(r["name"]),
                fmt_score(r["score"]),
                fmt_pct(r["rate"]),
                str(r["n"]),
                str(r["gap_n"]),
                "—" if r["score"] is None else fmt_score(r["score"] - TARGET_SCORE),
            ]
            for r in ctx["domain_rows"]
        ],
    )
    dim_table = table_html(
        ["评估维度", "达成率", "已达成", "能力项"],
        [
            [esc(r["name"]), fmt_pct(r["rate"]), "%d / %d" % (r["done"], r["n"]), str(r["n"])]
            for r in ctx["dim_rows"]
        ],
    )

    heat_head = "".join("<th>%s</th>" % esc(d) for d in CAPABILITY_DOMAINS)
    heat_body = []
    for r in ctx["team_rows"]:
        if r["n"] == 0:
            continue
        cells = ["<td>%s</td>" % esc(r["name"])]
        for d in CAPABILITY_DOMAINS:
            sc = r["domain_scores"].get(d) if d in (r["domains"] or []) else None
            cells.append(
                '<td class="%s">%s</td>' % (heat_class(sc), "—" if sc is None and d not in (r["domains"] or []) else fmt_score(sc))
            )
        heat_body.append("<tr>%s</tr>" % "".join(cells))
    heat_table = (
        "<table class=\"heat\"><thead><tr><th>科组 \\ 领域</th>%s</tr></thead><tbody>%s</tbody></table>"
        % (heat_head, "".join(heat_body) or '<tr><td colspan="7" class="muted">无</td></tr>')
    )

    plan_rows = table_html(
        ["计划月份", "未达成项数量"],
        [[("%d 月" % m), str(ctx["plan_dist"][m])] for m in PLAN_MONTHS]
        + [["未标记计划月份", str(ctx["unmarked"])]],
    )
    pred_rows = table_html(
        ["截止月份（计划项视为达成）", "预测全中心得分"],
        [[("%d 月" % m), fmt_score(ctx["pred_by_month"][m])] for m in PLAN_MONTHS],
    )

    new_html = ""
    if ctx["new_achieved"]:
        lis = []
        for log in ctx["new_achieved"][:40]:
            who = log.get("user") or log.get("operator") or log.get("actor") or "未记录操作者"
            when = log.get("time") or log.get("created_at") or ""
            act = log.get("action") or log.get("changes") or log
            lis.append("<li>%s · %s · %s</li>" % (esc(when), esc(who), esc(act)))
        new_html = "<ul class=\"list\">%s</ul>" % "".join(lis)
    else:
        new_html = '<div class="trend-empty">无历史月度快照，也无可用的本月新增达成清单。不虚构趋势。</div>'

    note_html = ""
    if ctx["notes_summary"]:
        lis = []
        for note in ctx["notes_summary"][:30]:
            text = "；".join(
                "%s=%s" % (k, v)
                for k, v in note.items()
                if v not in (None, "") and k.lower() not in ("id",)
            )
            lis.append("<li>%s</li>" % esc(text[:240]))
        note_html = "<ul class=\"list\">%s</ul>" % "".join(lis)
    else:
        note_html = '<p class="muted">库中暂无「未达成情况记录」文字（monthly_gap_notes 为空或不存在）。</p>'

    unmet_by_domain = defaultdict(int)
    unmet_by_dept = defaultdict(int)
    for x in ctx["unmet"]:
        unmet_by_domain[x.get("domain_cat") or "未分类"] += 1
        unmet_by_dept[x.get("dept") or "未标注部门"] += 1
    unmet_domain_table = table_html(
        ["领域", "未达成项"],
        [[esc(k), str(v)] for k, v in sorted(unmet_by_domain.items(), key=lambda kv: -kv[1])],
    )
    unmet_dept_table = table_html(
        ["部门（记录字段）", "未达成项"],
        [[esc(k), str(v)] for k, v in sorted(unmet_by_dept.items(), key=lambda kv: -kv[1])][:20],
    )

    suggestions = []
    if weak_d:
        suggestions.append(
            "优先领域：%s（得分 %s，未达成 %d 项）。" % (weak_d["name"], fmt_score(weak_d["score"]), weak_d["gap_n"])
        )
    if weak_t:
        suggestions.append(
            "优先科组：%s（得分 %s，未达成 %d 项）。" % (weak_t["name"], fmt_score(weak_t["score"]), weak_t["gap_n"])
        )
    if weak_dept:
        suggestions.append(
            "优先部门：%s（得分 %s）。" % (weak_dept["name"], fmt_score(weak_dept["score"]))
        )
    if ctx["unmarked"]:
        suggestions.append("有 %d 项未达成且未标记计划月份，建议先补计划再谈预测。" % ctx["unmarked"])
    if not suggestions:
        suggestions.append("按规则未形成额外优先级；保持现有达成项即可。")
    sug_html = "<ul class=\"list\">%s</ul>" % "".join("<li>%s</li>" % esc(s) for s in suggestions)

    team_list = "、".join(esc(t["name"]) for t in ctx["teams"][:40])
    if len(ctx["teams"]) > 40:
        team_list += " 等 %d 个科组" % len(ctx["teams"])
    dept_list = "、".join(esc(d["name"]) for d in ctx["dept_rows"]) or "无"
    biz_list = "、".join(esc(d["name"]) for d in ctx["biz_rows"]) or "无"

    level_counts = defaultdict(lambda: {"n": 0, "done": 0})
    for x in ctx["items"]:
        lv = str(x.get("level") or "未标注")
        level_counts[lv]["n"] += 1
        if is_achieved(x):
            level_counts[lv]["done"] += 1
    level_html = "；".join(
        "%s %d/%d" % (k, v["done"], v["n"]) for k, v in sorted(level_counts.items())
    )

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>测试能力成熟度月报 {esc(meta['period'])}</title>
<style>
body{{margin:0;background:#eef2f6;color:#1d2b3a;font:14px Arial,"Microsoft YaHei","PingFang SC",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:24px}}
header{{background:#173b63;color:#fff;padding:26px 32px;border-radius:8px}}
header h1{{margin:0 0 8px;font-size:26px}}
header .sub{{color:#c7d6e8;font-size:13px;line-height:1.7}}
.legend{{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}}
.tag{{display:inline-block;padding:3px 9px;border-radius:3px;font-size:12px;white-space:nowrap}}
.t-real{{background:#e3f3e6;color:#1d7a35;border:1px solid #9fd4ab}}
.t-demo{{background:#fff3d6;color:#a16207;border:1px solid #e8c97a}}
.t-ppt{{background:#e5eefc;color:#2756a6;border:1px solid #a9c4ea}}
.t-snap{{background:#eceff3;color:#5b6b7c;border:1px solid #c2ccd6}}
.toc{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 18px}}
.toc a{{background:#fff;border:1px solid #d7e0e8;border-radius:4px;padding:6px 10px;color:#173b63;text-decoration:none;font-size:13px}}
.chapter{{background:#fff;border:1px solid #d7e0e8;border-radius:6px;margin:0 0 16px;overflow:hidden}}
.ch-head{{display:flex;align-items:baseline;gap:10px;padding:13px 16px;background:#f6f9fb;border-bottom:1px solid #e4e9ee}}
.ch-no{{font-size:20px;font-weight:700;color:#173b63}}
.ch-title{{font-size:16px;font-weight:700;color:#173b63}}
.ch-body{{padding:14px 16px}}
.sec-title{{font-weight:700;margin:12px 0 6px;color:#173b63}}
.grid,.grid3,.grid4{{display:grid;gap:10px}}
.grid4{{grid-template-columns:repeat(4,1fr)}}
.grid3{{grid-template-columns:repeat(3,1fr)}}
.grid{{grid-template-columns:1fr 1fr;gap:12px}}
.card,.panel{{background:#fff;border:1px solid #d7e0e8;border-radius:6px;padding:16px}}
.card b{{display:block;color:#173b63;font-size:24px;margin-top:4px}}
.muted{{color:#647488;font-size:12px}}
.warn{{background:#fff8e8;border:1px solid #e8c97a;padding:10px 12px;border-radius:4px;color:#7a4b08;line-height:1.7}}
.demo-panel{{border:2px dashed #e8c97a;background:#fffdf5}}
.demo-card{{background:#fff8e8}}
table{{width:100%;border-collapse:collapse;background:#fff;margin:8px 0 12px}}
th,td{{padding:8px;border-bottom:1px solid #e4e9ee;text-align:left;font-size:13px}}
th{{background:#f1f5f8;color:#44576a;font-size:12px}}
.score{{font-weight:700;color:#173b63}}
.chart-row{{display:grid;grid-template-columns:110px 1fr 48px;align-items:center;gap:8px;margin:8px 0}}
.chart-row i{{display:block;height:16px;background:#287a8d;border-radius:2px}}
.pie{{width:130px;height:130px;border-radius:50%;margin:12px auto;background:conic-gradient(#287a8d 0 {pie}%, #e5ebf0 {pie}% 100%)}}
.trend-empty{{padding:22px;text-align:center;border:1px dashed #b7c4d0;color:#647488;background:#f8fafb}}
.list{{margin:6px 0 10px;padding-left:18px;line-height:1.7}}
.heat td.h-good{{background:#d8f3dc}}
.heat td.h-mid{{background:#eef6c9}}
.heat td.h-low{{background:#ffe8c2}}
.heat td.h-bad{{background:#ffd4d4}}
.heat td.h-na{{color:#94a3b8}}
footer{{color:#64748b;font-size:12px;margin:18px 0;line-height:1.7}}
@media(max-width:720px){{main{{padding:12px}}.grid,.grid3,.grid4{{grid-template-columns:1fr 1fr}}header h1{{font-size:20px}}}}
@media print{{body{{background:#fff}}main{{padding:0}}.chapter,.card,.panel{{box-shadow:none;break-inside:avoid}}}}
</style>
</head>
<body>
<main>
<header>
  <h1>测试能力成熟度月报</h1>
  <div class="sub">
    报告期 {esc(meta['period'])} · 生成时间 {esc(meta['generated_at'])} · 口径 {REPORT_VER}<br>
    数据源（只读）：{esc(meta['db_path'])}<br>
    库 SHA-256：{esc(meta['db_sha256'])} · 能力项 {oi['n']} · 科组 {len(ctx['teams'])} · 部门 {len(ctx['dept_rows'])} · 业务线 {len(ctx['biz_rows'])}<br>
    交付形态：单个可双击打开的 HTML · 不转 PPT
  </div>
</header>

<div class="legend">
  <span class="tag t-real">真实库计算</span>
  <span class="tag t-demo">临时演示 · 后续用真实数据替换</span>
  <span class="tag t-ppt">叙述参考</span>
  <span class="tag t-snap">真实快照积累</span>
</div>
<nav class="toc">
  <a href="#c1">01 报告简介</a>
  <a href="#c2">02 管理模式演进</a>
  <a href="#c3">03 总体成熟度观察</a>
  <a href="#c4">04 指标基准分析</a>
  <a href="#c5">05 优势短板</a>
  <a href="#c6">06 改进闭环</a>
  <a href="#c7">07 附录</a>
</nav>

<div class="chapter" id="c1">
  <div class="ch-head"><span class="ch-no">01</span><span class="ch-title">报告简介</span></div>
  <div class="ch-body">
    <div class="sec-title">1.1 指标定义 <span class="tag t-ppt">叙述参考</span></div>
    <p>评分公式（V2.0.18 已确认）：科组-领域得分 = 2级达成率×2 + 3级达成率 + 4级达成率（5级不计）。科组得分 = 所关联领域得分的算术平均。部门 / 业务线得分 = 关联科组得分等权平均。全中心总分 = 全部可计分科组等权平均。年度目标 3.0，满分 4.0。达成判定 0/1。能力项达成率 = 已达成条数 / 总条数。</p>
    <div class="sec-title">1.2 分析方法 <span class="tag t-ppt">叙述参考</span></div>
    <p>聚合路径：科组 → 部门 → 业务线。对标基准：同部门内科组平均、全中心科组平均。业务线按关联科组交集计算，不把未关联科组并入。未关联领域不参与该科组计分。</p>
    <div class="sec-title">1.3 报告数据及结论说明 <span class="tag t-real">真实库</span></div>
    <p>快照时间 {esc(meta['generated_at'])}。业务库路径与哈希见页头。除第 4.5 节「测试质量结果」明确标记为临时演示外，所有得分、达成率、排名均由本库动态计算，不编造、不引用未核验的网上数据。</p>
    <div class="sec-title">1.4 能力基线概览 <span class="tag t-real">真实库</span></div>
    <p>六大领域：{'、'.join(CAPABILITY_DOMAINS)}。能力项 {oi['n']}（已达成 {oi['done']}，未达成 {oi['gap']}）。等级分布：{esc(level_html)}。</p>
    <p>部门：{dept_list}</p>
    <p>业务线：{biz_list}</p>
    <p>科组：{team_list}</p>
  </div>
</div>

<div class="chapter" id="c2">
  <div class="ch-head"><span class="ch-no">02</span><span class="ch-title">管理模式演进（2025 → 2026）</span></div>
  <div class="ch-body">
    <div class="sec-title">2.1 从专项评分到持续能力经营 <span class="tag t-ppt">叙述参考</span></div>
    <p>2025 痛点：科组自选范围、目标自行选取、结果无法对比、季度跟踪、年底集中验收、偏重进度管理。2026 转向统一供给与持续运营：统一能力清单、统一目标 3.0、实时跟踪、达成即验收。</p>
    <div class="sec-title">2.2 能力设计 <span class="tag t-ppt">叙述参考</span></div>
    <p>能力 Owner 统一设计评估维度能力，并统一分发至各涉域科组。六大领域（软件 / 硬件 / 机械 / EMC / 合规 / 环境可靠性）同域统一口径，年度目标一致为 3.0。</p>
    <div class="sec-title">2.3 监控运营与递进能力阶 <span class="tag t-ppt">叙述参考</span></div>
    <p>实时跟踪、达成即验收、落地辅导。能力阶：2 级打基础基底，3 级作为年度重点，4 级对应数字化 / AI，构成年度目标合集。5 级不计入本期成熟度得分。</p>
    <div class="sec-title">2.4 价值兑现 <span class="tag t-ppt">叙述参考</span></div>
    <p>可诊断（识别差距）、可对比（科组 / 部门 / 业务横向比较）、可引导（分层改进建议）。三类角色：科组与部门负责人看短板与计划；能力 Owner 看领域供给与达成；测试管理者看中心目标风险。</p>
  </div>
</div>

<div class="chapter" id="c3">
  <div class="ch-head"><span class="ch-no">03</span><span class="ch-title">总体成熟度观察</span></div>
  <div class="ch-body">
    <div class="sec-title">3.1 总体达成现状 <span class="tag t-real">真实库</span></div>
    <div class="grid4">
      <div class="card">全中心总分<b>{fmt_score(overall)}</b><span class="muted">科组等权 · 目标 3.0</span></div>
      <div class="card">能力项达成率<b>{fmt_pct(oi['rate'])}</b><span class="muted">{oi['done']} / {oi['n']}</span></div>
      <div class="card">距目标差距<b>{fmt_score(gap) if gap is not None else '—'}</b><span class="muted">实际 − 3.0</span></div>
      <div class="card">未达成能力<b>{oi['gap']}</b><span class="muted">待改进范围</span></div>
    </div>
    <p><b>数据分析：</b>{esc(overall_note)}</p>
    <div class="sec-title">3.2 本期变化 <span class="tag t-real">真实库</span></div>
    <p>{esc(change_note)}</p>
    {new_html}
    <div class="sec-title">3.3 预计与计划 <span class="tag t-real">真实库</span></div>
    <p>预测规则：仅把「未达成且计划月份不晚于该月」的能力项视为达成后，按同一套公式重算全中心得分。未标记计划月份的项不进入预测。不把 due（预计交付）自动当成计划月份。</p>
    <div class="grid">{pred_rows}{plan_rows}</div>
    <div class="sec-title">3.4 年度目标达成风险评估 <span class="tag t-real">真实库</span></div>
    <p>{esc(risk_text)}</p>
  </div>
</div>

<div class="chapter" id="c4">
  <div class="ch-head"><span class="ch-no">04</span><span class="ch-title">指标基准分析（对标）</span></div>
  <div class="ch-body">
    <div class="sec-title">4.1 领域维度得分 <span class="tag t-real">真实库</span></div>
    <div class="grid">
      <div><h3>领域得分</h3>{domain_bars}</div>
      <div><h3>总体能力项达成</h3><div class="pie"></div><div class="muted" style="text-align:center">已达成 {oi['done']} / {oi['n']}（{fmt_pct(oi['rate'])}）</div>
        <p><b>数据分析：</b>{esc(('领域最高 %s（%s），最低 %s（%s）。' % (best_d['name'], fmt_score(best_d['score']), weak_d['name'], fmt_score(weak_d['score']))) if best_d and weak_d else '暂无可比较领域得分。')}</p>
      </div>
    </div>
    {domain_table}
    <div class="sec-title">4.2 评估维度达成率 <span class="tag t-real">真实库</span></div>
    {dim_table}
    <div class="sec-title">4.3 科组基准排名 <span class="tag t-real">真实库</span></div>
    <p>分档：领先 = 全中心前 10%；达标 = 得分 ≥ 3.0；发展 = 2.0–3.0；基础 = 后 10% 或 &lt; 2.0。</p>
    {team_table}
    <div class="sec-title">4.4 部门 / 业务线对比 <span class="tag t-real">真实库</span></div>
    <p>部门与业务线均为关联科组得分等权平均（与 V2.0.18 组织能力概览口径一致），不是把全部能力项合并后再算。</p>
    {dept_table}
    {biz_table}
    {demo_quality_block()}
  </div>
</div>

<div class="chapter" id="c5">
  <div class="ch-head"><span class="ch-no">05</span><span class="ch-title">组织能力分布与优势短板</span></div>
  <div class="ch-body">
    <div class="sec-title">5.1 优势分析 <span class="tag t-real">真实库</span></div>
    <ul class="list">
      <li>最高科组：{esc(best_t['name'] + '（' + fmt_score(best_t['score']) + '）') if best_t else '无'}</li>
      <li>最高部门：{esc(best_dept['name'] + '（' + fmt_score(best_dept['score']) + '）') if best_dept else '无'}</li>
      <li>最高业务线：{esc(best_biz['name'] + '（' + fmt_score(best_biz['score']) + '）') if best_biz else '无'}</li>
      <li>最高领域：{esc(best_d['name'] + '（' + fmt_score(best_d['score']) + '）') if best_d else '无'}</li>
      <li>领先科组（前 10%）：{esc('、'.join(t['name'] for t in leading) or '样本不足，未标注领先档')}</li>
    </ul>
    <div class="sec-title">5.2 短板分析 <span class="tag t-real">真实库</span></div>
    <ul class="list">
      <li>最低科组：{esc(weak_t['name'] + '（' + fmt_score(weak_t['score']) + '）') if weak_t else '无'}</li>
      <li>最低部门：{esc(weak_dept['name'] + '（' + fmt_score(weak_dept['score']) + '）') if weak_dept else '无'}</li>
      <li>最低业务线：{esc(weak_biz['name'] + '（' + fmt_score(weak_biz['score']) + '）') if weak_biz else '无'}</li>
      <li>最低领域：{esc(weak_d['name'] + '（' + fmt_score(weak_d['score']) + '）') if weak_d else '无'}</li>
      <li>基础档 / 后 10% 科组：{esc('、'.join(t['name'] for t in lagging) or '无')}</li>
    </ul>
    <div class="sec-title">5.3 领域 × 组织热力分布 <span class="tag t-real">真实库</span></div>
    <p>单元格为该科组在该领域的成熟度得分。灰色「—」表示该科组未关联该领域，不参与计分。</p>
    {heat_table}
  </div>
</div>

<div class="chapter" id="c6">
  <div class="ch-head"><span class="ch-no">06</span><span class="ch-title">改进闭环与行动跟踪</span></div>
  <div class="ch-body">
    <div class="sec-title">6.1 未达成项现状 <span class="tag t-real">真实库</span></div>
    <div class="grid">{unmet_domain_table}{unmet_dept_table}</div>
    <p class="sec-title">未达成情况记录摘要</p>
    {note_html}
    <div class="sec-title">6.2 改进计划分布 <span class="tag t-real">真实库</span></div>
    {plan_rows}
    <div class="sec-title">6.3 改进建议 <span class="tag t-real">真实库</span></div>
    <p>下列建议由「最弱领域 × 最弱组织 × 未标记计划」规则生成，不是主观编写。</p>
    {sug_html}
  </div>
</div>

<div class="chapter" id="c7">
  <div class="ch-head"><span class="ch-no">07</span><span class="ch-title">附录</span></div>
  <div class="ch-body">
    <div class="sec-title">7.1 指标口径与版本 <span class="tag t-ppt">叙述参考</span></div>
    <p>报告版本 {REPORT_VER}。计分与 V2.0.18 确认口径一致：科组-领域 = 2级达成率×2 + 3级达成率 + 4级达成率；科组 = 关联领域平均；部门 / 业务线 / 全中心 = 科组等权平均。能力分组键 = 领域 + Owner + 评估维度 + 细分能力。领域归并：安规/合规/认证 → 合规；可靠性/环境 → 环境可靠性。</p>
    <div class="sec-title">7.2 术语表 <span class="tag t-ppt">叙述参考</span></div>
    <p>领域：软件、硬件、机械、EMC、合规、环境可靠性。评估维度：能力项上的 dimension 字段。等级：2/3/4 级计入得分，5 级不计。科组 / 部门 / 业务线来自 teams 与 org_units 及关联表。</p>
    <div class="sec-title">7.3 数据质量与真实 / 演示边界 <span class="tag t-real">真实库</span></div>
    <ul class="list">
      <li>真实库：第 1.3–1.4、3、4.1–4.4、5、6 章全部数字。</li>
      <li>临时演示：仅 4.5 测试质量结果（平均缺陷数、reopen 率占位）。</li>
      <li>叙述参考：第 1.1–1.2、2、7.1–7.2 的管理模式文字。</li>
      <li>快照积累：本次生成同时写入只增不改的月度快照 JSON，供 2027/2028 年历史对比；本期不做虚构的上半年对比。</li>
      <li>未关联领域：不计入该科组得分，热力图显示为 —。</li>
    </ul>
  </div>
</div>

<footer>
生成本地只读，不修改业务库。输出目录不覆盖既有月报版本。落地时请把 --db 指向生成时点 5000 正在使用的正式库。
</footer>
</main>
</body>
</html>
"""


def write_snapshot(out_dir, period, payload):
    snap_dir = out_dir / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    target = snap_dir / ("%s.json" % period)
    if target.exists():
        stamped = snap_dir / ("%s-%s.json" % (period, datetime.now().strftime("%H%M%S")))
        stamped.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return stamped, False
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target, True


def main(argv=None):
    parser = argparse.ArgumentParser(description="生成测试能力成熟度月报 HTML")
    parser.add_argument("--db", help="maturity.db 路径（优先传当前 5000 正式库）")
    parser.add_argument("--out-dir", help="输出目录（默认 E:\\raft\\monthly-reports\\v2.0.18 或脚本旁 v2.0.18）")
    parser.add_argument("--period", default=date.today().strftime("%Y-%m"), help="报告期 YYYY-MM")
    args = parser.parse_args(argv)

    db_path = resolve_db(args.db)
    out_dir = resolve_out_dir(args.out_dir)
    data = load_db(db_path)
    ctx = compute(data, args.period)
    meta = {
        "period": args.period,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "db_path": str(db_path),
        "db_sha256": sha256_file(db_path),
        "app_meta": data["meta"],
    }
    html = render_html(ctx, meta)
    html_path = out_dir / "测试能力成熟度月报.html"
    html_path.write_text(html, encoding="utf-8")
    snap_path, first = write_snapshot(out_dir, args.period, snapshot_payload(ctx, meta))
    readme = out_dir / "README.txt"
    readme.write_text(
        "\n".join(
            [
                "测试能力成熟度月报 %s" % REPORT_VER,
                "双击打开：%s" % html_path.name,
                "生成命令示例：",
                '  py -3.10 generate_v2_0_18.py --db "<当前5000正式库maturity.db>" --out-dir "%s"'
                % out_dir,
                "不要写死 V2.0.17 路径；18 切到 5000 后传 18 的库。",
                "快照：%s（%s）" % (snap_path.name, "本期首份" if first else "同月追加，未覆盖旧快照"),
                "库 SHA-256：%s" % meta["db_sha256"],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print("HTML\t%s" % html_path)
    print("SNAPSHOT\t%s" % snap_path)
    print("DB\t%s" % db_path)
    print("SHA256\t%s" % meta["db_sha256"])
    print("ITEMS\t%s" % ctx["overall_items"]["n"])
    print("SCORE\t%s" % fmt_score(ctx["overall_score"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
