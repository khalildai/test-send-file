from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.environ.get("MATURITY_DB_PATH", DATA_DIR / "maturity.db"))
WRITE_LOCK = threading.RLock()

app = Flask(__name__, static_folder=None)
app.json.ensure_ascii = False


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
            INSERT OR IGNORE INTO app_meta(key, value) VALUES ('revision', '0');
            INSERT OR IGNORE INTO app_meta(key, value) VALUES ('initialized', '0');
            """
        )


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


@app.after_request
def add_headers(response):
    response.headers["Cache-Control"] = "no-store" if request.path.startswith("/api/") else "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/")
def index():
    return send_from_directory(BASE_DIR / "static", "index.html")


@app.get("/<path:name>")
def static_file(name: str):
    return send_from_directory(BASE_DIR / "static", name)


@app.get("/api/health")
def health():
    with connect() as db:
        revision = current_revision(db)
    return jsonify({"ok": True, "version": "V2.0.10", "revision": revision})


@app.get("/api/state")
def get_state():
    with connect() as db:
        return jsonify(load_state(db))


@app.put("/api/state")
def put_state():
    payload = request.get_json(silent=True)
    try:
        validate_state(payload)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    expected = request.headers.get("If-Match")
    if expected is None or not expected.isdigit():
        return jsonify({"error": "缺少有效的版本号"}), 428
    with WRITE_LOCK:
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")
            actual = current_revision(db)
            if int(expected) != actual:
                db.rollback()
                return jsonify({"error": "数据已被其他用户更新，请刷新后重试", "revision": actual}), 409
            new_revision = actual + 1
            replace_state(db, payload, new_revision)
            db.commit()
    return jsonify({"ok": True, "revision": new_revision})


init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("MATURITY_PORT", "5000")), threaded=True)
