from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class SessionStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS pending_actions (
                    action_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    args_json TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    args_preview_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    error_json TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS tool_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    action_id TEXT,
                    tool_name TEXT NOT NULL,
                    command_json TEXT NOT NULL,
                    stdout_text TEXT,
                    stderr_text TEXT,
                    ok INTEGER NOT NULL,
                    error_category TEXT,
                    duration_ms INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

    def ensure_session(self, session_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO sessions(session_id) VALUES (?)",
                (session_id,),
            )

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.ensure_session(session_id)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages(session_id, role, content, metadata_json)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, role, content, json.dumps(metadata or {}, ensure_ascii=False)),
            )

    def get_messages(self, session_id: str, limit: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, metadata_json, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        messages = []
        for row in reversed(rows):
            messages.append(
                {
                    "role": row["role"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata_json"] or "{}"),
                    "created_at": row["created_at"],
                }
            )
        return messages

    def create_pending_action(
        self,
        session_id: str,
        tool_name: str,
        args: dict[str, Any],
        summary: str,
        args_preview: dict[str, Any],
    ) -> dict[str, Any]:
        action_id = str(uuid.uuid4())
        payload = {
            "action_id": action_id,
            "session_id": session_id,
            "tool_name": tool_name,
            "summary": summary,
            "args": args,
            "args_preview": args_preview,
            "status": "pending",
        }
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO pending_actions(
                    action_id, session_id, tool_name, args_json, summary, args_preview_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    action_id,
                    session_id,
                    tool_name,
                    json.dumps(args, ensure_ascii=False),
                    summary,
                    json.dumps(args_preview, ensure_ascii=False),
                    "pending",
                ),
            )
        return payload

    def get_pending_action(self, action_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT action_id, session_id, tool_name, args_json, summary,
                       args_preview_json, status, result_json, error_json,
                       created_at, updated_at
                FROM pending_actions
                WHERE action_id = ?
                """,
                (action_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "action_id": row["action_id"],
            "session_id": row["session_id"],
            "tool_name": row["tool_name"],
            "args": json.loads(row["args_json"]),
            "summary": row["summary"],
            "args_preview": json.loads(row["args_preview_json"]),
            "status": row["status"],
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "error": json.loads(row["error_json"]) if row["error_json"] else None,
        }

    def get_latest_pending_action_for_session(self, session_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT action_id
                FROM pending_actions
                WHERE session_id = ? AND status = 'pending'
                ORDER BY rowid DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return self.get_pending_action(str(row["action_id"]))

    def update_pending_action(
        self,
        action_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE pending_actions
                SET status = ?, result_json = ?, error_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE action_id = ?
                """,
                (
                    status,
                    json.dumps(result, ensure_ascii=False) if result is not None else None,
                    json.dumps(error, ensure_ascii=False) if error is not None else None,
                    action_id,
                ),
            )

    def log_tool_call(
        self,
        *,
        session_id: str | None,
        action_id: str | None,
        tool_name: str,
        command: list[str],
        stdout_text: str,
        stderr_text: str,
        ok: bool,
        error_category: str | None,
        duration_ms: int,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tool_logs(
                    session_id, action_id, tool_name, command_json,
                    stdout_text, stderr_text, ok, error_category, duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    action_id,
                    tool_name,
                    json.dumps(command, ensure_ascii=False),
                    stdout_text,
                    stderr_text,
                    1 if ok else 0,
                    error_category,
                    duration_ms,
                ),
            )
