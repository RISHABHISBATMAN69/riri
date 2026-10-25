from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AuditLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    detail_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    agent_session_id TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def record(
        self,
        conversation_id: str,
        event_type: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_events
                    (conversation_id, event_type, detail_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    event_type,
                    json.dumps(detail or {}, sort_keys=True),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

    def agent_session(self, conversation_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT agent_session_id FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        return row["agent_session_id"] if row else None

    def save_agent_session(self, conversation_id: str, session_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations (conversation_id, agent_session_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    agent_session_id = excluded.agent_session_id,
                    updated_at = excluded.updated_at
                """,
                (conversation_id, session_id, datetime.now(timezone.utc).isoformat()),
            )

    def recent(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT conversation_id, event_type, detail_json, created_at
                FROM audit_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        events = []
        for row in rows:
            events.append(
                {
                    "conversation_id": row["conversation_id"],
                    "event_type": row["event_type"],
                    "detail": json.loads(row["detail_json"]),
                    "created_at": row["created_at"],
                }
            )
        return events
