from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class ReachAIStore:
    def __init__(self, db_path: str = "reachai.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS outreach (
                    outreach_id TEXT PRIMARY KEY,
                    target_name TEXT,
                    company TEXT,
                    status TEXT NOT NULL,
                    message TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approval_tokens (
                    token TEXT PRIMARY KEY,
                    outreach_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    used INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY(outreach_id) REFERENCES outreach(outreach_id)
                )
                """
            )

    def save_outreach(self, record: Dict[str, Any]) -> Dict[str, Any]:
        if "created_at" not in record:
            record["created_at"] = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO outreach (outreach_id, target_name, company, status, message, created_at)
                VALUES (:outreach_id, :target_name, :company, :status, :message, :created_at)
                ON CONFLICT(outreach_id)
                DO UPDATE SET
                    target_name = excluded.target_name,
                    company = excluded.company,
                    status = excluded.status,
                    message = excluded.message,
                    created_at = excluded.created_at
                """,
                record,
            )
        return self.get_outreach(record["outreach_id"])

    def get_outreach(self, outreach_id: str) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM outreach WHERE outreach_id = ?",
                (outreach_id,),
            ).fetchone()
        if row is None:
            return {}
        return dict(row)

    def create_approval_token(self, outreach_id: str) -> str:
        token = secrets.token_urlsafe(16)
        created_at = datetime.now(timezone.utc).isoformat()
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO approval_tokens (token, outreach_id, status, used, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(token) DO NOTHING
                """,
                (token, outreach_id, "PENDING_APPROVAL", 0, created_at, expires_at),
            )
        return token

    def validate_approval_token(self, token: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT used, expires_at FROM approval_tokens WHERE token = ?",
                (token,),
            ).fetchone()
        if row is None:
            return False
        if row["used"]:
            return False
        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            return False
        return True

    def approve_token(self, token: str) -> bool:
        if not self.validate_approval_token(token):
            return False
        with self._connect() as conn:
            row = conn.execute(
                "SELECT outreach_id FROM approval_tokens WHERE token = ?",
                (token,),
            ).fetchone()
            if row is None:
                return False
            outreach_id = row["outreach_id"]
            conn.execute(
                "UPDATE approval_tokens SET used = 1, status = 'APPROVED' WHERE token = ?",
                (token,),
            )
            conn.execute(
                "UPDATE outreach SET status = 'APPROVED' WHERE outreach_id = ?",
                (outreach_id,),
            )
        return True

    def reject_token(self, token: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT outreach_id FROM approval_tokens WHERE token = ?",
                (token,),
            ).fetchone()
            if row is None:
                return False
            outreach_id = row["outreach_id"]
            conn.execute(
                "UPDATE approval_tokens SET used = 1, status = 'REJECTED' WHERE token = ?",
                (token,),
            )
            conn.execute(
                "UPDATE outreach SET status = 'REJECTED' WHERE outreach_id = ?",
                (outreach_id,),
            )
        return True
