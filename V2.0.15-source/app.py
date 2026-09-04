from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, session


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.environ.get("MATURITY_DB_PATH", DATA_DIR / "maturity.db"))
WRITE_LOCK = threading.RLock()

app = Flask(__name__, static_folder=None)
app.json.ensure_ascii = False
app.secret_key = os.environ.get("MATURITY_SECRET", secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(days=7)


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 15000")
    return connection


def init_db() -> None:
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS capabilities (
                id TEXT PRIMARY KEY,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS teams (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                domains TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS org_units (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL CHECK(kind IN ('department', 'business')),
                name TEXT NOT NULL,
                UNIQUE(kind, name)
            );
            CREATE TABLE IF NOT EXISTS org_team_relations (
                org_id TEXT NOT NULL REFERENCES org_units(id) ON DELETE CASCADE,
                team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
                PRIMARY KEY (org_id, team_id)
            );
            CREATE TABLE IF NOT EXISTS change_logs (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','owner','biz')),
                display_name TEXT
            );
            CREATE TABLE IF NOT EXISTS audit_logs (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                operator TEXT NOT NULL,
                role TEXT NOT NULL,
                target TEXT NOT NULL,
                field TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT
            );
            CREATE TABLE IF NOT EXISTS monthly_gap_notes (
                note_key TEXT PRIMARY KEY,
                month TEXT NOT NULL,
                identity_key TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                snapshot TEXT,
                achieved INTEGER,
                updated_at TEXT NOT NULL,
                updated_by TEXT
            );
            INSERT OR IGNORE INTO app_meta(key, value) VALUES ('revision', '0');
            INSERT OR IGNORE INTO app_meta(key, value) VALUES ('initialized', '0');
            """)
        admin_salt = secrets.token_hex(8)
        admin_hash = hashlib.sha256(('123qweasd' + admin_salt).encode()).hexdigest()
        db.execute(
            "INSERT OR IGNORE INTO users(username, password_hash, salt, role, display_name) VALUES (?, ?, ?, 'admin', '管理员')",
            ('admin', admin_hash, admin_salt),
        )
        # Owner/业务采用固定角色行和共享角色密码，不创建个人账号。
        owner_salt = secrets.token_hex(8)
        owner_hash = hashlib.sha256(('owner123' + owner_salt).encode()).hexdigest()
        db.execute(
            "INSERT OR IGNORE INTO users(username, password_hash, salt, role, display_name) VALUES (?, ?, ?, 'owner', '能力Owner')",
            ('owner', owner_hash, owner_salt),
        )
        biz_salt = secrets.token_hex(8)
        biz_hash = hashlib.sha256(('biz123' + biz_salt).encode()).hexdigest()
        db.execute(
            "INSERT OR IGNORE INTO users(username, password_hash, salt, role, display_name) VALUES (?, ?, ?, 'biz', '业务')",
            ('biz', biz_hash, biz_salt),
        )
        cols = {row[1] for row in db.execute("PRAGMA table_info(monthly_gap_notes)")}
        if "snapshot" not in cols:
            db.execute("ALTER TABLE monthly_gap_notes ADD COLUMN snapshot TEXT")
        if "achieved" not in cols:
            db.execute("ALTER TABLE monthly_gap_notes ADD COLUMN achieved INTEGER")


def json_value(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def parse_json(value, fallback):
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def current_revision(db: sqlite3.Connection) -> int:
    row = db.execute("SELECT value FROM app_meta WHERE key='revision'").fetchone()
    return int(row["value"] if row else 0)


def load_state(db: sqlite3.Connection) -> dict:
    settings = {
        row["key"]: parse_json(row["value"], None)
        for row in db.execute("SELECT key, value FROM app_settings")
    }
    teams = [
        {"id": row["id"], "name": row["name"], "domains": parse_json(row["domains"], [])}
        for row in db.execute("SELECT id, name, domains FROM teams ORDER BY rowid")
    ]
    units = list(db.execute("SELECT id, kind, name FROM org_units ORDER BY rowid"))
    relations = {}
    for row in db.execute("SELECT org_id, team_id FROM org_team_relations ORDER BY rowid"):
        relations.setdefault(row["org_id"], []).append(row["team_id"])
    config = {
        "teams": teams,
        "departments": [
            {"id": row["id"], "name": row["name"], "teamIds": relations.get(row["id"], [])}
            for row in units if row["kind"] == "department"
        ],
        "businesses": [
            {"id": row["id"], "name": row["name"], "teamIds": relations.get(row["id"], [])}
            for row in units if row["kind"] == "business"
        ],
    }
    initialized = db.execute("SELECT value FROM app_meta WHERE key='initialized'").fetchone()["value"] == "1"
    return {
        "initialized": initialized,
        "revision": current_revision(db),
        "data": [parse_json(row["payload"], {}) for row in db.execute("SELECT payload FROM capabilities ORDER BY rowid")],
        "changeLogs": [parse_json(row["payload"], {}) for row in db.execute("SELECT payload FROM change_logs ORDER BY seq DESC")],
        "configData": config,
        "asOf": settings.get("asOf"),
        "insightLock": bool(settings.get("insightLock", False)),
        "insightTexts": settings.get("insightTexts", []),
        "tipEdits": settings.get("tipEdits", {"dept": {}, "team": {}}),
        "rawColumnLabels": settings.get("rawColumnLabels"),
        "comparison": settings.get("comparison"),
    }


METRIC_WEIGHTS = {"2级": 2, "3级": 1, "4级": 1}


def maturity_metric_results(state: dict) -> dict:
    """Build team, department and business scores from one shared metric grain."""
    rows = state.get("data") or []
    config = state.get("configData") or {}
    teams = config.get("teams") or []
    team_by_id = {str(team.get("id")): team for team in teams}
    dimensions = sorted({str(row.get("dimension") or "") for row in rows if row.get("dimension")})

    def team_score(team: dict, domain: str, dimension: str):
        matching = [
            row for row in rows
            if row.get("team") == team.get("name")
            and row.get("domain") == domain
            and row.get("dimension") == dimension
            and row.get("level") in METRIC_WEIGHTS
        ]
        if not matching:
            return None
        levels = {}
        score = 0.0
        for level, weight in METRIC_WEIGHTS.items():
            level_rows = [row for row in matching if row.get("level") == level]
            achieved_count = sum(1 for row in level_rows if int(row.get("achieved") or 0) == 1)
            total = len(level_rows)
            contribution = achieved_count / total * weight if total else 0.0
            levels[level] = {
                "achieved": achieved_count,
                "total": total,
                "weight": weight,
                "contribution": round(contribution, 4),
            }
            score += contribution
        return {"score": round(score, 4), "levels": levels, "capabilityCount": len(matching)}

    team_metrics = []
    for team in teams:
        for domain in team.get("domains") or []:
            for dimension in dimensions:
                result = team_score(team, domain, dimension)
                if result is not None:
                    team_metrics.append({
                        "scope": "team",
                        "entityId": team.get("id"),
                        "entity": team.get("name"),
                        "domain": domain,
                        "dimension": dimension,
                        **result,
                    })

    def aggregate_units(kind: str, units: list):
        output = []
        for unit in units:
            names = {team_by_id.get(str(team_id), {}).get("name") for team_id in unit.get("teamIds") or []}
            names.discard(None)
            pairs = {(item["domain"], item["dimension"]) for item in team_metrics if item["entity"] in names}
            for domain, dimension in sorted(pairs):
                samples = [
                    item for item in team_metrics
                    if item["entity"] in names and item["domain"] == domain and item["dimension"] == dimension
                ]
                if samples:
                    output.append({
                        "scope": kind,
                        "entityId": unit.get("id"),
                        "entity": unit.get("name"),
                        "domain": domain,
                        "dimension": dimension,
                        "score": round(sum(item["score"] for item in samples) / len(samples), 4),
                        "teamCount": len(samples),
                        "teams": [item["entity"] for item in samples],
                    })
        return output

    department_metrics = aggregate_units("department", config.get("departments") or [])
    business_metrics = aggregate_units("business", config.get("businesses") or [])

    def averages(scope: str, metrics: list):
        output = []
        pairs = {(item["domain"], item["dimension"]) for item in metrics}
        for domain, dimension in sorted(pairs):
            samples = [item for item in metrics if item["domain"] == domain and item["dimension"] == dimension]
            output.append({
                "scope": scope,
                "domain": domain,
                "dimension": dimension,
                "score": round(sum(item["score"] for item in samples) / len(samples), 4),
                "sampleCount": len(samples),
            })
        return output

    return {
        "target": 3.0,
        "maximum": 4.0,
        "formula": "2级达成率×2 + 3级达成率 + 4级达成率",
        "team": team_metrics,
        "department": department_metrics,
        "business": business_metrics,
        "averages": {
            "team": averages("team", team_metrics),
            "department": averages("department", department_metrics),
            "business": averages("business", business_metrics),
        },
    }


def validate_state(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ValueError("请求内容必须是 JSON 对象")
    if not isinstance(payload.get("data"), list):
        raise ValueError("能力数据格式无效")
    config = payload.get("configData")
    if not isinstance(config, dict) or any(not isinstance(config.get(key), list) for key in ("teams", "departments", "businesses")):
        raise ValueError("组织关系格式无效")
    ids = [str(row.get("id", "")).strip() for row in config["teams"]]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("科组 ID 为空或重复")
    names = [str(row.get("name", "")).strip() for row in config["teams"]]
    if any(not item for item in names) or len(names) != len(set(names)):
        raise ValueError("科组名称为空或重复")
    valid_ids = set(ids)
    for kind in ("departments", "businesses"):
        for unit in config[kind]:
            if not str(unit.get("id", "")).strip() or not str(unit.get("name", "")).strip():
                raise ValueError("部门或业务的 ID/名称不能为空")
            if any(team_id not in valid_ids for team_id in unit.get("teamIds", [])):
                raise ValueError("组织关系引用了不存在的科组")


def replace_state(db: sqlite3.Connection, payload: dict, new_revision: int) -> None:
    config = payload["configData"]
    db.execute("DELETE FROM org_team_relations")
    db.execute("DELETE FROM org_units")
    db.execute("DELETE FROM teams")
    db.execute("DELETE FROM capabilities")
    db.execute("DELETE FROM change_logs")
    db.execute("DELETE FROM app_settings")

    db.executemany(
        "INSERT INTO capabilities(id, payload) VALUES (?, ?)",
        [(str(row.get("id") or f"cap-{index + 1}"), json_value(row)) for index, row in enumerate(payload["data"])],
    )
    db.executemany(
        "INSERT INTO teams(id, name, domains) VALUES (?, ?, ?)",
        [(str(row["id"]), str(row["name"]), json_value(row.get("domains", []))) for row in config["teams"]],
    )
    for kind, key in (("department", "departments"), ("business", "businesses")):
        for row in config[key]:
            unit_id = str(row["id"])
            db.execute("INSERT INTO org_units(id, kind, name) VALUES (?, ?, ?)", (unit_id, kind, str(row["name"])))
            db.executemany(
                "INSERT INTO org_team_relations(org_id, team_id) VALUES (?, ?)",
                [(unit_id, str(team_id)) for team_id in row.get("teamIds", [])],
            )
    db.executemany(
        "INSERT INTO change_logs(payload) VALUES (?)",
        [(json_value(row),) for row in reversed(payload.get("changeLogs", [])[:500])],
    )
    settings = {
        key: payload.get(key)
        for key in ("asOf", "insightLock", "insightTexts", "tipEdits", "rawColumnLabels", "comparison")
    }
    db.executemany(
        "INSERT INTO app_settings(key, value) VALUES (?, ?)",
        [(key, json_value(value)) for key, value in settings.items()],
    )
    db.execute("UPDATE app_meta SET value=? WHERE key='revision'", (str(new_revision),))
    db.execute("UPDATE app_meta SET value='1' WHERE key='initialized'")




# ---------- 权限 ----------
ROLE_FIELD_PERMS = {
    "admin": None,          # 全部
    "owner": None,          # 能力属性与达成数据均可修改
    "biz": "achievement",   # 仅达成/预期
}
CAPABILITY_FIELDS = {"domain", "owner", "dimension", "sub", "description", "delivered", "due", "level", "stage", "digital"}
ACHIEVEMENT_FIELDS = {"achieved", "plannedMonth", "expectedSep", "expectedDec"}
SERVER_OWNED_FIELDS = {"achievedAt", "plannedMonthUpdatedAt"}


def apply_server_timestamps(old_rows: list, new_rows: list) -> None:
    """Normalize plan months and own the audit timestamps on the server."""
    old_by_id = {str(row.get("id")): row for row in old_rows}
    old_by_key = {_row_key(row): row for row in old_rows}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for row in new_rows:
        previous = old_by_id.get(str(row.get("id"))) or old_by_key.get(_row_key(row)) or {}
        old_achieved = int(previous.get("achieved") or 0)
        new_achieved = int(row.get("achieved") or 0)
        row["achievedAt"] = (
            now if new_achieved == 1 and old_achieved != 1
            else previous.get("achievedAt") if new_achieved == 1
            else None
        )

        raw_month = row.get("plannedMonth")
        if raw_month in (None, ""):
            planned_month = None
        else:
            try:
                planned_month = int(raw_month)
            except (TypeError, ValueError) as error:
                raise ValueError("预计落地月份必须为 1-12 月") from error
            if planned_month < 1 or planned_month > 12:
                raise ValueError("预计落地月份必须为 1-12 月")
        old_month = previous.get("plannedMonth")
        old_month = int(old_month) if old_month not in (None, "") else None
        row["plannedMonth"] = planned_month
        row["plannedMonthUpdatedAt"] = (
            now if planned_month != old_month else previous.get("plannedMonthUpdatedAt")
        )


def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((password + salt).encode()).hexdigest()


def current_user(db: sqlite3.Connection) -> dict | None:
    username = session.get("username")
    if not username:
        return None
    row = db.execute("SELECT username, role, display_name FROM users WHERE username=?", (username,)).fetchone()
    return {"username": row["username"], "role": row["role"], "displayName": row["display_name"]} if row else None


def require_login():
    if "username" not in session:
        raise PermissionError("未登录")


def enforce_field_perms(old_rows: list, new_rows: list):
    role = session.get("role")
    if role == "admin" or ROLE_FIELD_PERMS.get(role) is None:
        return
    allowed = CAPABILITY_FIELDS if role == "owner" else ACHIEVEMENT_FIELDS
    old_map = {str(r.get("id")): r for r in old_rows}
    team_keys = set()
    for r in new_rows:
        key = (r.get("domain"), r.get("owner"), r.get("dimension"), r.get("sub"))
        team_keys.add(key)
    for r in new_rows:
        prev = old_map.get(str(r.get("id")))
        if prev is None:
            prev = next((o for o in old_rows if (o.get("domain"), o.get("owner"), o.get("dimension"), o.get("sub")) == (r.get("domain"), r.get("owner"), r.get("dimension"), r.get("sub")) and o.get("team") == r.get("team")), None)
        fields = set(r.keys()) | (set(prev.keys()) if prev else set())
        for f in fields - allowed - SERVER_OWNED_FIELDS:
            if prev is None:
                if f in ACHIEVEMENT_FIELDS and role == "owner":
                    continue
                if role == "biz" and f in CAPABILITY_FIELDS:
                    if prev is None and f == "team":
                        continue
                    continue
            new_v = r.get(f)
            old_v = (prev or {}).get(f)
            if new_v != old_v:
                msg = "业务方无权限修改能力相关数据" if role == "biz" else "当前角色无权限修改该内容"
                raise PermissionError(msg)


@app.after_request
def add_headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/")
def index():
    return send_from_directory(BASE_DIR / "static", "index.html")


@app.get("/<path:name>")
def static_file(name: str):
    return send_from_directory(BASE_DIR / "static", name)




@app.post("/api/auth/login")
def auth_login():
    body = request.get_json(silent=True) or {}
    password = str(body.get("password", ""))
    role = str(body.get("role", "")).strip()
    if role in ("owner", "biz"):
        # 角色密码登录（无用户名），匹配固定角色行。
        with connect() as db:
            row = db.execute(
                "SELECT username, password_hash, salt, role, display_name FROM users WHERE username=? AND role=?",
                (role, role),
            ).fetchone()
        if not row or hash_password(password, row["salt"]) != row["password_hash"]:
            return jsonify({"error": "该角色密码不正确"}), 401
    else:
        username = str(body.get("username", "")).strip()
        if not username or not password:
            return jsonify({"error": "请输入用户名和密码"}), 400
        with connect() as db:
            row = db.execute("SELECT username, password_hash, salt, role, display_name FROM users WHERE username=?", (username,)).fetchone()
        if not row or hash_password(password, row["salt"]) != row["password_hash"]:
            return jsonify({"error": "用户名或密码错误"}), 401
    session.permanent = True
    session["username"] = row["username"]
    session["role"] = row["role"]
    return jsonify({"ok": True, "user": {"username": row["username"], "role": row["role"], "displayName": row["display_name"]}})


@app.post("/api/auth/logout")
def auth_logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/auth/me")
def auth_me():
    with connect() as db:
        user = current_user(db)
    if not user:
        return jsonify({"user": None})
    return jsonify({"user": user})


@app.get("/api/users")
def list_users():
    with connect() as db:
        user = current_user(db)
        if not user or user["role"] != "admin":
            return jsonify({"error": "仅管理员可管理用户"}), 403
        rows = db.execute("SELECT username, role, display_name FROM users ORDER BY username").fetchall()
    return jsonify({"users": [{"username": r["username"], "role": r["role"], "displayName": r["display_name"]} for r in rows]})


@app.post("/api/users")
def create_user():
    return jsonify({"error": "本版本已改为角色密码模式（能力Owner/业务共用角色密码，无个人账号），不支持新增用户"}), 400


@app.post("/api/users/<username>/password")
def reset_password(username):
    body = request.get_json(silent=True) or {}
    password = str(body.get("password", ""))
    if not password:
        return jsonify({"error": "新密码不能为空"}), 400
    with connect() as db:
        user = current_user(db)
        if not user or (user["role"] != "admin" and user["username"] != username):
            return jsonify({"error": "无权修改该用户密码"}), 403
        salt = secrets.token_hex(8)
        db.execute("UPDATE users SET password_hash=?, salt=? WHERE username=?", (hash_password(password, salt), salt, username))
        db.commit()
    return jsonify({"ok": True})


@app.delete("/api/users/<username>")
def delete_user(username):
    return jsonify({"error": "本版本已改为角色密码模式，不支持删除用户"}), 400


@app.get("/api/health")
def health():
    with connect() as db:
        revision = current_revision(db)
        user = current_user(db)
    return jsonify({"ok": True, "version": "V2.0.15", "revision": revision, "user": user})


@app.get("/api/state")
def get_state():
    with connect() as db:
        return jsonify(load_state(db))


@app.get("/api/metrics/maturity")
def get_maturity_metrics():
    with connect() as db:
        state = load_state(db)
    return jsonify(maturity_metric_results(state))


AUDIT_FIELD_LABELS = {
    "domain": "领域", "owner": "能力Owner", "dimension": "评估维度", "sub": "细分能力",
    "description": "能力建设内容描述", "delivered": "是否已交付", "due": "预计交付日期",
    "team": "科组", "dept": "三级部门", "level": "年度等级", "stage": "年度目标",
    "digital": "数字化验收", "achieved": "达成情况", "expectedSep": "9月预期达成",
    "expectedDec": "12月预期达成", "plannedMonth": "预计落地月份",
    "riskOverride": "风险手工修正", "yearData": "年度数据",
    "configLabels": "列名/标签配置",
}
AUDIT_IGNORE_FIELDS = {"id", "achievedAt", "plannedMonthUpdatedAt"}


def _audit_value(v):
    if v is None or v == "":
        return "(空)"
    if isinstance(v, bool):
        return "是" if v else "否"
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False, sort_keys=True)
    return str(v)


def _row_target(row: dict) -> str:
    parts = [row.get("domain") or "", row.get("sub") or ""]
    target = " / ".join(p for p in parts if p)
    if row.get("team"):
        target = f"{target} · {row['team']}" if target else str(row["team"])
    return target or "(未命名)"


def _row_key(row: dict):
    return (
        str(row.get("domain") or ""), str(row.get("owner") or ""), str(row.get("dimension") or ""),
        str(row.get("sub") or ""), str(row.get("team") or ""),
    )


def compute_audit_entries(old_rows: list, new_rows: list, old_config: dict, new_config: dict) -> list:
    """字段级 diff：返回待写入 audit_logs 的 tuple 列表（ts/operator/role 由调用方填充）。"""
    entries = []
    old_by_key = {}
    for r in old_rows:
        old_by_key[_row_key(r)] = r
    new_keys = set()
    for r in new_rows:
        key = _row_key(r)
        new_keys.add(key)
        prev = old_by_key.get(key)
        if prev is None:
            entries.append((_row_target(r), "新增记录", "(无)", _audit_value("新增")))
            continue
        for f in (set(prev.keys()) | set(r.keys())) - AUDIT_IGNORE_FIELDS:
            old_v, new_v = prev.get(f), r.get(f)
            if old_v != new_v:
                entries.append((_row_target(r), AUDIT_FIELD_LABELS.get(f, f), _audit_value(old_v), _audit_value(new_v)))
    for key, r in old_by_key.items():
        if key not in new_keys:
            entries.append((_row_target(r), "删除记录", _audit_value("删除"), "(无)"))
    # 组织关系配置 diff（摘要级）
    def _config_snapshot(config: dict) -> dict:
        snap = {}
        for kind, key in (("科组", "teams"), ("部门", "departments"), ("业务线", "businesses")):
            rows = config.get(key) or []
            snap[kind] = {str(x.get("name")): sorted(str(t) for t in (x.get("teamIds") or [])) for x in rows}
        return snap
    old_snap, new_snap = _config_snapshot(old_config or {}), _config_snapshot(new_config or {})
    for kind in ("科组", "部门", "业务线"):
        old_names, new_names = set(old_snap.get(kind, {})), set(new_snap.get(kind, {}))
        for name in sorted(new_names - old_names):
            entries.append((f"组织关系配置 · {kind}", f"新增{kind}", "(无)", name))
        for name in sorted(old_names - new_names):
            entries.append((f"组织关系配置 · {kind}", f"删除{kind}", name, "(无)"))
        for name in sorted(old_names & new_names):
            if old_snap[kind][name] != new_snap[kind][name]:
                o, n = old_snap[kind][name], new_snap[kind][name]
                added = ",".join(sorted(set(n) - set(o))) or "无"
                removed = ",".join(sorted(set(o) - set(n))) or "无"
                entries.append((f"组织关系配置 · {kind} · {name}", "关联科组变化", f"移除: {removed}", f"新增: {added}"))
    return entries


@app.put("/api/state")
def put_state():
    with connect() as db:
        user = current_user(db)
    if not user:
        return jsonify({"error": "未登录，请先登录后再修改数据"}), 401
    payload = request.get_json(silent=True)
    try:
        validate_state(payload)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    if user["role"] != "admin":
        with connect() as db:
            old_rows = [json.loads(r[0]) for r in db.execute("SELECT payload FROM capabilities ORDER BY rowid")]
        try:
            enforce_field_perms(old_rows, payload.get("data", []))
        except PermissionError as error:
            return jsonify({"error": str(error)}), 403
    expected = request.headers.get("If-Match")
    if expected is None or not expected.isdigit():
        return jsonify({"error": "缺少有效的版本号"}), 428
    if isinstance(payload.get("changeLogs"), list) and payload["changeLogs"]:
        payload["changeLogs"] = [dict(log, operator=(user.get("displayName") or user["username"])) if isinstance(log, dict) else log for log in payload["changeLogs"][:1]] + payload["changeLogs"][1:]
    with WRITE_LOCK:
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            actual = current_revision(db)
            if int(expected) != actual:
                db.rollback()
                return jsonify({"error": "数据已被其他用户更新，请刷新后重试", "revision": actual}), 409
            old_rows = [json.loads(r[0]) for r in db.execute("SELECT payload FROM capabilities ORDER BY rowid")]
            # 组织关系快照（部门/业务线含关联科组；科组仅名单）
            old_config = {"teams": [], "departments": [], "businesses": []}
            old_config["departments"] = [dict(name=n, teamIds=json.loads(rel or "[]")) for n, rel in db.execute(
                "SELECT o.name, (SELECT json_group_array(rt.team_id) FROM org_team_relations rt WHERE rt.org_id=o.id) FROM org_units o WHERE o.kind='department'")]
            old_config["businesses"] = [dict(name=n, teamIds=json.loads(rel or "[]")) for n, rel in db.execute(
                "SELECT o.name, (SELECT json_group_array(rt.team_id) FROM org_team_relations rt WHERE rt.org_id=o.id) FROM org_units o WHERE o.kind='business'")]
            old_config["teams"] = [dict(name=n, teamIds=[]) for (n,) in db.execute("SELECT name FROM teams")]
            new_revision = actual + 1
            try:
                apply_server_timestamps(old_rows, payload.get("data", []))
            except ValueError as error:
                db.rollback()
                return jsonify({"error": str(error)}), 400
            audit_entries = compute_audit_entries(old_rows, payload.get("data", []), old_config, payload.get("configData", {}))
            replace_state(db, payload, new_revision)
            if audit_entries:
                import datetime as _dt
                ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db.executemany(
                    "INSERT INTO audit_logs(ts, operator, role, target, field, old_value, new_value) VALUES (?,?,?,?,?,?,?)",
                    [(ts, user.get("displayName") or user["username"], user["role"], t, f, o, n) for (t, f, o, n) in audit_entries],
                )
            db.commit()
    return jsonify({"ok": True, "revision": new_revision})


@app.get("/api/audit-logs")
def get_audit_logs():
    with connect() as db:
        rows = db.execute(
            "SELECT seq, ts, operator, role, target, field, old_value, new_value FROM audit_logs ORDER BY seq DESC LIMIT 500"
        ).fetchall()
    role_label = {"admin": "管理员", "owner": "能力Owner", "biz": "业务"}
    return jsonify({"logs": [
        {"seq": r["seq"], "time": r["ts"], "operator": r["operator"], "role": role_label.get(r["role"], r["role"]),
         "target": r["target"], "field": r["field"], "oldValue": r["old_value"], "newValue": r["new_value"]}
        for r in rows
    ]})


def _gap_note_key(month: str, identity_key: str) -> str:
    return f"{month}::{identity_key}"


def _valid_month(value: str) -> bool:
    if not isinstance(value, str) or len(value) != 7 or value[4] != "-":
        return False
    year, month = value[:4], value[5:]
    return year.isdigit() and month.isdigit() and 1 <= int(month) <= 12


def _system_month() -> str:
    return datetime.now().strftime("%Y-%m")


@app.get("/api/monthly-gap-notes")
def get_monthly_gap_notes():
    with connect() as db:
        user = current_user(db)
        if not user:
            return jsonify({"error": "未登录，请先登录后再查看未达成项记录"}), 401
        rows = db.execute(
            "SELECT note_key, month, identity_key, note, snapshot, achieved, updated_at, updated_by FROM monthly_gap_notes"
        ).fetchall()
    current = _system_month()
    items = {}
    notes = {}
    for row in rows:
        snapshot = parse_json(row["snapshot"], None) if row["snapshot"] else None
        items[row["note_key"]] = {
            "month": row["month"],
            "identityKey": row["identity_key"],
            "note": row["note"] or "",
            "snapshot": snapshot,
            "achieved": row["achieved"],
            "updatedAt": row["updated_at"],
            "updatedBy": row["updated_by"],
            "sealed": bool(row["month"] and row["month"] < current),
        }
        notes[row["note_key"]] = row["note"] or ""
    return jsonify({
        "schemaVersion": 3,
        "currentMonth": current,
        "identityFields": ["domain", "owner", "dimension", "sub", "team"],
        "notes": notes,
        "items": items,
    })


@app.put("/api/monthly-gap-notes")
def put_monthly_gap_notes():
    payload = request.get_json(silent=True) or {}
    with connect() as db:
        user = current_user(db)
    if not user:
        return jsonify({"error": "未登录，请先登录后再保存未达成项记录"}), 401
    current = _system_month()
    month = str(payload.get("month") or "").strip()
    if not _valid_month(month):
        return jsonify({"error": "请提供有效自然月"}), 400
    if month > current:
        return jsonify({"error": "未到该月份，不能提前编辑"}), 400
    if month < current:
        return jsonify({"error": "该月份已封存，不能再修改"}), 403
    items = payload.get("items")
    notes = payload.get("notes")
    if items is None and isinstance(notes, dict):
        items = [
            {"identityKey": key.split("::", 1)[-1], "note": value, "snapshot": None, "achieved": None}
            for key, value in notes.items() if isinstance(key, str) and key.startswith(f"{month}::")
        ]
    if not isinstance(items, list):
        return jsonify({"error": "items 必须是数组"}), 400
    operator = user.get("displayName") or user["username"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cleaned = []
    for item in items:
        if not isinstance(item, dict):
            return jsonify({"error": "记录格式无效"}), 400
        identity_key = str(item.get("identityKey") or "").strip()
        if not identity_key:
            return jsonify({"error": "缺少能力项标识"}), 400
        note = "" if item.get("note") is None else str(item.get("note"))
        if len(note) > 800:
            return jsonify({"error": "单条文字记录不能超过 800 字"}), 400
        snapshot = item.get("snapshot") if isinstance(item.get("snapshot"), dict) else None
        achieved = item.get("achieved")
        if achieved is not None:
            achieved = 1 if achieved in (1, "1", True) else 0
        note_key = _gap_note_key(month, identity_key)
        cleaned.append((note_key, month, identity_key, note, json_value(snapshot) if snapshot else None, achieved))
    with WRITE_LOCK:
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for note_key, month_value, identity_key, note, snapshot, achieved in cleaned:
                db.execute(
                    """
                    INSERT INTO monthly_gap_notes(note_key, month, identity_key, note, snapshot, achieved, updated_at, updated_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(note_key) DO UPDATE SET
                        note=excluded.note,
                        snapshot=COALESCE(excluded.snapshot, monthly_gap_notes.snapshot),
                        achieved=COALESCE(excluded.achieved, monthly_gap_notes.achieved),
                        updated_at=excluded.updated_at,
                        updated_by=excluded.updated_by
                    """,
                    (note_key, month_value, identity_key, note, snapshot, achieved, now, operator),
                )
            db.commit()
    return jsonify({"ok": True, "savedAt": now, "operator": operator, "month": month, "currentMonth": current})


@app.delete("/api/audit-logs")
def clear_audit_logs():
    with connect() as db:
        user = current_user(db)
    if not user or user["role"] != "admin":
        return jsonify({"error": "仅管理员可清空修改记录"}), 403
    with connect() as db:
        db.execute("DELETE FROM audit_logs")
        db.commit()
    return jsonify({"ok": True})


init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("MATURITY_PORT", "5000")), threaded=True)
