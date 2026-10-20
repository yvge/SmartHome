"""SQLite persistence layer.

Deliberately dependency-free (stdlib sqlite3) and synchronous: the demo's
workload is tiny, and a single WAL-mode connection keeps the project easy to
run anywhere. All JSON columns are encoded/decoded at this boundary.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

SCHEMA = """
CREATE TABLE IF NOT EXISTS app_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    room         TEXT NOT NULL,
    room_id      TEXT NOT NULL,
    type         TEXT NOT NULL,
    online       INTEGER NOT NULL DEFAULT 1,
    icon         TEXT NOT NULL DEFAULT 'cpu',
    sort_order   INTEGER NOT NULL DEFAULT 0,
    properties   TEXT NOT NULL DEFAULT '{}',
    capabilities TEXT NOT NULL DEFAULT '[]',
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scenes (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    icon        TEXT NOT NULL DEFAULT 'sparkles',
    description TEXT NOT NULL DEFAULT '',
    condition   TEXT,
    steps       TEXT NOT NULL DEFAULT '[]',
    fallback    TEXT NOT NULL DEFAULT '[]',
    builtin     INTEGER NOT NULL DEFAULT 0,
    enabled     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    title      TEXT NOT NULL DEFAULT '新的对话',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    meta       TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);

CREATE TABLE IF NOT EXISTS executions (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL DEFAULT '',
    kind        TEXT NOT NULL DEFAULT 'chat',
    title       TEXT NOT NULL DEFAULT '',
    input       TEXT NOT NULL DEFAULT '',
    intent      TEXT NOT NULL DEFAULT '{}',
    tool_calls  TEXT NOT NULL DEFAULT '[]',
    trace       TEXT NOT NULL DEFAULT '[]',
    result      TEXT NOT NULL DEFAULT '{}',
    status      TEXT NOT NULL DEFAULT 'success',
    duration_ms INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_executions_created ON executions(created_at DESC);

CREATE TABLE IF NOT EXISTS kb_entries (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL DEFAULT 'intent',
    text        TEXT NOT NULL,
    intent      TEXT NOT NULL DEFAULT '',
    category    TEXT NOT NULL DEFAULT '',
    device_type TEXT NOT NULL DEFAULT '',
    answer      TEXT NOT NULL DEFAULT '',
    metadata    TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL
);
"""


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_id(prefix: str = "") -> str:
    token = uuid.uuid4().hex[:10]
    return f"{prefix}{token}" if prefix else token


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(self.path), check_same_thread=False, timeout=15.0
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute("PRAGMA busy_timeout=5000;")

    # ------------------------------------------------------------- core
    def init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def execute_many(self, sql: str, rows: Iterable[Sequence[Any]]) -> None:
        with self._lock:
            self._conn.executemany(sql, rows)
            self._conn.commit()

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    # ------------------------------------------------------------- meta
    def get_meta(self, key: str) -> str | None:
        row = self.query_one("SELECT value FROM app_meta WHERE key = ?", (key,))
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO app_meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    # ---------------------------------------------------------- devices
    def load_devices(self) -> list[dict[str, Any]]:
        rows = self.query("SELECT * FROM devices ORDER BY sort_order, id")
        for row in rows:
            row["online"] = bool(row["online"])
            row["properties"] = _loads(row["properties"], {})
            row["capabilities"] = _loads(row["capabilities"], [])
        return rows

    def save_device(self, device: dict[str, Any]) -> None:
        self.execute(
            """
            INSERT INTO devices(id, name, room, room_id, type, online, icon,
                                sort_order, properties, capabilities, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name, room = excluded.room,
                room_id = excluded.room_id, type = excluded.type,
                online = excluded.online, icon = excluded.icon,
                sort_order = excluded.sort_order,
                properties = excluded.properties,
                capabilities = excluded.capabilities,
                updated_at = excluded.updated_at
            """,
            (
                device["id"],
                device["name"],
                device["room"],
                device["room_id"],
                device["type"],
                int(device.get("online", True)),
                device.get("icon", "cpu"),
                int(device.get("sort_order", 0)),
                _dumps(device.get("properties", {})),
                _dumps(device.get("capabilities", [])),
                device.get("updated_at", now_iso()),
            ),
        )

    def save_devices(self, devices: Iterable[dict[str, Any]]) -> None:
        for device in devices:
            self.save_device(device)

    # ----------------------------------------------------------- scenes
    @staticmethod
    def _decode_scene(row: dict[str, Any]) -> dict[str, Any]:
        row["condition"] = _loads(row["condition"], None)
        row["steps"] = _loads(row["steps"], [])
        row["fallback"] = _loads(row["fallback"], [])
        row["builtin"] = bool(row["builtin"])
        row["enabled"] = bool(row["enabled"])
        return row

    def load_scenes(self) -> list[dict[str, Any]]:
        rows = self.query("SELECT * FROM scenes ORDER BY builtin DESC, created_at, id")
        return [self._decode_scene(row) for row in rows]

    def get_scene(self, scene_id: str) -> dict[str, Any] | None:
        row = self.query_one("SELECT * FROM scenes WHERE id = ?", (scene_id,))
        return self._decode_scene(row) if row else None

    def save_scene(self, scene: dict[str, Any]) -> None:
        now = now_iso()
        self.execute(
            """
            INSERT INTO scenes(id, name, icon, description, condition, steps,
                               fallback, builtin, enabled, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name, icon = excluded.icon,
                description = excluded.description,
                condition = excluded.condition, steps = excluded.steps,
                fallback = excluded.fallback, enabled = excluded.enabled,
                updated_at = excluded.updated_at
            """,
            (
                scene["id"],
                scene["name"],
                scene.get("icon", "sparkles"),
                scene.get("description", ""),
                _dumps(scene["condition"]) if scene.get("condition") else None,
                _dumps(scene.get("steps", [])),
                _dumps(scene.get("fallback", [])),
                int(scene.get("builtin", False)),
                int(scene.get("enabled", True)),
                scene.get("created_at", now),
                now,
            ),
        )

    def delete_scene(self, scene_id: str) -> bool:
        cur = self.execute("DELETE FROM scenes WHERE id = ? AND builtin = 0", (scene_id,))
        return cur.rowcount > 0

    # --------------------------------------------------------- messages
    def ensure_session(self, session_id: str, title: str = "新的对话") -> None:
        now = now_iso()
        self.execute(
            "INSERT OR IGNORE INTO sessions(id, title, created_at, updated_at) "
            "VALUES(?, ?, ?, ?)",
            (session_id, title or "新的对话", now, now),
        )

    def touch_session(self, session_id: str) -> None:
        self.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?", (now_iso(), session_id)
        )

    def rename_session(self, session_id: str, title: str) -> None:
        self.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title[:60], now_iso(), session_id),
        )

    def add_message(
        self, session_id: str, role: str, content: str, meta: dict[str, Any] | None = None,
        *, ensure_session: bool = True,
    ) -> int:
        if ensure_session:
            self.ensure_session(session_id, title=content[:24] if role == "user" else "新的对话")
        cur = self.execute(
            "INSERT INTO messages(session_id, role, content, meta, created_at) "
            "VALUES(?, ?, ?, ?, ?)",
            (session_id, role, content, _dumps(meta or {}), now_iso()),
        )
        self.touch_session(session_id)
        return int(cur.lastrowid or 0)

    def list_messages(self, session_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.query(
            "SELECT * FROM (SELECT * FROM messages WHERE session_id = ? "
            "ORDER BY id DESC LIMIT ?) ORDER BY id ASC",
            (session_id, limit),
        )
        for row in rows:
            row["meta"] = _loads(row["meta"], {})
        return rows

    def recent_history(self, session_id: str, limit: int = 8) -> list[dict[str, str]]:
        rows = self.list_messages(session_id, limit=limit)
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.query(
            "SELECT s.*, (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) "
            "AS message_count FROM sessions s ORDER BY s.updated_at DESC LIMIT ?",
            (limit,),
        )
        return rows

    def delete_session(self, session_id: str) -> None:
        self.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        self.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    # -------------------------------------------------------- executions
    def add_execution(self, execution: dict[str, Any]) -> None:
        self.execute(
            """
            INSERT INTO executions(id, session_id, kind, title, input, intent,
                                   tool_calls, trace, result, status,
                                   duration_ms, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                execution["id"],
                execution.get("session_id", ""),
                execution.get("kind", "chat"),
                execution.get("title", ""),
                execution.get("input", ""),
                _dumps(execution.get("intent", {})),
                _dumps(execution.get("tool_calls", [])),
                _dumps(execution.get("trace", [])),
                _dumps(execution.get("result", {})),
                execution.get("status", "success"),
                int(execution.get("duration_ms", 0)),
                execution.get("created_at", now_iso()),
            ),
        )

    @staticmethod
    def _decode_execution(row: dict[str, Any]) -> dict[str, Any]:
        for key, default in (
            ("intent", {}), ("tool_calls", []), ("trace", []), ("result", {})
        ):
            row[key] = _loads(row[key], default)
        return row

    def list_executions(self, limit: int = 30) -> list[dict[str, Any]]:
        rows = self.query(
            "SELECT * FROM executions ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (limit,),
        )
        return [self._decode_execution(row) for row in rows]

    def get_execution(self, execution_id: str) -> dict[str, Any] | None:
        row = self.query_one("SELECT * FROM executions WHERE id = ?", (execution_id,))
        return self._decode_execution(row) if row else None

    # --------------------------------------------------------------- kb
    def load_kb(self) -> list[dict[str, Any]]:
        rows = self.query("SELECT * FROM kb_entries ORDER BY created_at, id")
        for row in rows:
            row["metadata"] = _loads(row["metadata"], {})
        return rows

    def save_kb_entry(self, entry: dict[str, Any]) -> None:
        self.execute(
            """
            INSERT INTO kb_entries(id, kind, text, intent, category, device_type,
                                   answer, metadata, created_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                kind = excluded.kind, text = excluded.text,
                intent = excluded.intent, category = excluded.category,
                device_type = excluded.device_type, answer = excluded.answer,
                metadata = excluded.metadata
            """,
            (
                entry["id"],
                entry.get("kind", "intent"),
                entry["text"],
                entry.get("intent", ""),
                entry.get("category", ""),
                entry.get("device_type", ""),
                entry.get("answer", ""),
                _dumps(entry.get("metadata", {})),
                entry.get("created_at", now_iso()),
            ),
        )

    def save_kb_entries(self, entries: Iterable[dict[str, Any]]) -> None:
        for entry in entries:
            self.save_kb_entry(entry)

    def count_kb(self) -> int:
        row = self.query_one("SELECT COUNT(*) AS c FROM kb_entries")
        return int(row["c"]) if row else 0

    # ------------------------------------------------------------ stats
    def stats(self) -> dict[str, int]:
        tables = ("devices", "scenes", "messages", "executions", "kb_entries")
        result: dict[str, int] = {}
        for table in tables:
            row = self.query_one(f"SELECT COUNT(*) AS c FROM {table}")
            result[table] = int(row["c"]) if row else 0
        return result
