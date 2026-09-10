"""Filter self-check for V2.0.26d2 temp demo. Run after migrate with a copied V2.0.26 db."""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

import app

DB = Path(__file__).resolve().parent / "data" / "maturity.db"
EMPTY_TEAMS = (
    "工业机器人软件测试组",
    "工业机器人整机产品测试组",
    "电柜测试及系统架构能力组",
)
DELETED_TEAMS = ("四关节测试组", "六关节测试组")
REMAPPED = {
    "工业机器人软件测试组": "机器人平台软件测试组",
    "工业机器人整机产品测试组": "工艺及解决方案测试组",
    "电柜测试及系统架构能力组": "电柜及整机性能测试组",
}
ALIASES = {
    "大型传动": "大型传动测试组",
    "人形机器人测试组": "人形机器人产品测试组",
    "视觉测试组": "视觉解决方案及产品测试组",
    "机器人平台软件测试组": "工业机器人软件测试组",
    "电柜及整机性能测试组": "电柜测试及系统架构能力组",
    "工艺及解决方案测试组": "工业机器人整机产品测试组",
}
CAPABILITY_DOMAINS = ["软件", "硬件", "机械", "环境可靠性", "安规准入", "EMC"]


def load_caps(conn: sqlite3.Connection) -> list[dict]:
    rows = []
    for row in conn.execute("SELECT payload FROM capabilities"):
        payload = json.loads(row["payload"])
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def main() -> int:
    app.init_db()
    app.migrate_capability_team_ids()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    teams = {row["name"]: row["id"] for row in conn.execute("SELECT id, name FROM teams")}
    caps = load_caps(conn)
    names = Counter(str(c.get("team") or "") for c in caps)
    failed = []

    for old in DELETED_TEAMS:
        n = names.get(old, 0)
        if n:
            failed.append(f"deleted team still has {n} rows: {old}")

    for new_name, old_name in REMAPPED.items():
        team_id = str(teams.get(new_name) or "")
        if not team_id:
            failed.append(f"missing org team: {new_name}")
            continue
        matched = [c for c in caps if str(c.get("teamId") or "") == team_id]
        leftover = names.get(old_name, 0)
        if leftover:
            failed.append(f"{old_name} still unmapped: {leftover}")
        if new_name in EMPTY_TEAMS and not matched:
            failed.append(f"{new_name} still has 0 bound rows")

    scene = [c for c in caps if str(c.get("dimension") or "").strip() == "场景化测试"]
    if len(scene) < 2:
        failed.append(f"场景化测试 too few: {len(scene)}")

    fan = [c for c in caps if str(c.get("owner") or "").strip() == "范方旭"]
    if not fan:
        failed.append("owner 范方旭 has 0 rows")

    unassigned = [c for c in caps if not c.get("teamId") and str(c.get("team") or "") == "未关联科组"]
    print(f"caps={len(caps)} scene={len(scene)} fan={len(fan)} unassigned={len(unassigned)}")

    teams_full = [
        {"id": row["id"], "name": row["name"], "domains": json.loads(row["domains"])}
        for row in conn.execute("SELECT id, name, domains FROM teams")
    ]
    units = list(conn.execute("SELECT id, kind, name FROM org_units"))
    rel = {}
    for row in conn.execute("SELECT org_id, team_id FROM org_team_relations"):
        rel.setdefault(row["org_id"], []).append(row["team_id"])
    departments = [
        {"id": row["id"], "name": row["name"], "teamIds": rel.get(row["id"], [])}
        for row in units if row["kind"] == "department"
    ]
    config = {"teams": teams_full, "departments": departments}

    def team_id_by_name(name):
        for t in teams_full:
            if t["name"] == name:
                return t["id"]
        return None

    def row_team_id(row):
        raw = "" if row.get("teamId") in (None, "") else str(row.get("teamId"))
        if raw and any(str(t["id"]) == raw for t in teams_full):
            return raw
        aliased = ALIASES.get(row.get("team"), row.get("team"))
        return team_id_by_name(aliased) or team_id_by_name(row.get("team")) or raw or None

    def domain_cat(domain):
        domain = domain or ""
        if re.search(r"安规|合规|认证", domain):
            return "合规"
        if re.search(r"可靠性|环境", domain):
            return "环境可靠性"
        return domain if domain in CAPABILITY_DOMAINS else domain

    def applies(group_items, team_name, team_filter_all):
        want_id = team_id_by_name(team_name)
        if any((row_team_id(item) and want_id and str(row_team_id(item)) == str(want_id)) for item in group_items):
            return True
        unassigned_group = all(not row_team_id(item) for item in group_items)
        if not unassigned_group and not team_filter_all:
            return False
        team = next(t for t in teams_full if t["name"] == team_name)
        return domain_cat(group_items[0].get("domain")) in (team.get("domains") or [])

    def groups_of(rows):
        grouped = {}
        for row in rows:
            key = "||".join(str(row.get(k) or "").strip() for k in ("domain", "owner", "dimension", "sub"))
            grouped.setdefault(key, []).append(row)
        return grouped

    alpha = next(d for d in departments if "α实验室" in d["name"])
    alpha_teams = [t["name"] for t in teams_full if t["id"] in set(alpha["teamIds"])]
    fan_groups = groups_of(fan)
    visible = [
        key for key, items in fan_groups.items()
        if any(applies(items, team, True) for team in alpha_teams)
    ]
    print(f"FAN x ALPHA visible groups={len(visible)} {visible}")
    if len(visible) != 2:
        failed.append(f"范方旭×α实验室 should show 2 software 场景化测试, got {len(visible)}")
    if any("软件" not in key for key in visible):
        failed.append(f"范方旭×α实验室 leaked non-software {visible}")

    software_unassigned = [c for c in unassigned if c.get("domain") == "软件" and c.get("dimension") == "场景化测试"]
    software_teams = [t["name"] for t in teams_full if "软件" in (t.get("domains") or [])]
    soft_groups = groups_of(software_unassigned)
    seen = [
        key for key, items in soft_groups.items()
        if any(applies(items, team, False) for team in software_teams)
    ]
    print(f"domain=软件 unassigned 场景化测试 groups={len(seen)}")
    if len(seen) != 2:
        failed.append(f"筛选软件 场景化测试 should be 2, got {len(seen)}")

    human = "人形机器人产品测试组"
    software_team = "工业机器人软件测试组"
    human_rows = [c for c in caps if str(c.get("team") or "") == human]
    leaked = 0
    for items in groups_of(human_rows).values():
        if applies(items, software_team, False):
            leaked += 1
    if leaked:
        failed.append(f"selected {software_team} still paints {leaked} 人形 groups")

    # Simulate chip click: value=teamId, label=name. 整机 must not show 软件组.
    zhengji = "工业机器人整机产品测试组"
    ruanjian = "工业机器人软件测试组"
    zid = team_id_by_name(zhengji)
    rid = team_id_by_name(ruanjian)
    if not zid or not rid or zid == rid:
        failed.append("整机/软件 teamId missing or collided")
    else:
        click_id = str(zid)  # chip data-v
        click_name = next(t["name"] for t in teams_full if str(t["id"]) == click_id)
        if click_name != zhengji:
            failed.append(f"click id {click_id} resolved to {click_name} not {zhengji}")
        matched = [c for c in caps if str(row_team_id(c) or "") == click_id]
        leaked_soft = [c for c in matched if str(row_team_id(c) or "") == str(rid)]
        names = {str(c.get("team") or "") for c in matched}
        print(f"CLICK {zhengji} id={click_id} n={len(matched)} names={names}")
        if leaked_soft:
            failed.append(f"click 整机 leaked {len(leaked_soft)} 软件组 rows")
        if ruanjian in names:
            failed.append("click 整机 still shows 工业机器人软件测试组")
        if click_name == ruanjian:
            failed.append("chip id for 整机 bound to 软件组")
        # every org team: click id -> only that team's bound rows
        for t in teams_full:
            tid = str(t["id"])
            rows = [c for c in caps if str(row_team_id(c) or "") == tid]
            other = {str(c.get("team") or "") for c in rows} - {t["name"]}
            if other:
                failed.append(f"click {t['name']} leaked {other}")

    # Click-sim: every department -> only that dept's teams
    team_by_id = {str(t["id"]): t for t in teams_full}
    for d in departments:
        expected = {team_by_id[str(tid)]["name"] for tid in d["teamIds"] if str(tid) in team_by_id}
        cols = set()
        for t in teams_full:
            if t["name"] in expected:
                cols.add(t["name"])
        if cols != expected:
            failed.append(f"click dept {d['name']} cols={cols} expected={expected}")
        leaked = [c for c in caps if str(c.get("team") or "") not in expected and str(row_team_id(c) or "") in {str(tid) for tid in d["teamIds"]}]
        print(f"CLICK dept {d['name']} teams={len(expected)}")

    # Click-sim: each domain chip
    for domain in ("软件", "硬件", "机械", "EMC", "安规准入", "环境可靠性"):
        rows = [c for c in caps if c.get("domain") == domain]
        if not rows:
            failed.append(f"click domain {domain} has 0 rows")
            continue
        print(f"CLICK domain {domain} n={len(rows)}")

    # Click-sim: 电柜组 must not show 软件组
    cabinet = "电柜测试及系统架构能力组"
    cid = team_id_by_name(cabinet)
    if cid:
        cab_rows = [c for c in caps if str(row_team_id(c) or "") == str(cid)]
        if any(str(c.get("team") or "") == ruanjian for c in cab_rows):
            failed.append("click 电柜组 leaked 软件组")
        print(f"CLICK {cabinet} n={len(cab_rows)}")

    if failed:
        print("SELFCHECK FAIL")
        for item in failed:
            print("-", item)
        return 1
    print("SELFCHECK PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
