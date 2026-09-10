"""Filter self-check for V2.0.26d1 temp demo. Run after migrate with a copied V2.0.26 db."""
from __future__ import annotations

import json
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
    if failed:
        print("SELFCHECK FAIL")
        for item in failed:
            print("-", item)
        return 1
    print("SELFCHECK PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
