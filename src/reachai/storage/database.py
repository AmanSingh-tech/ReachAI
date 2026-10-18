import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List


class Database:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            from reachai.config import get_settings

            db_path = get_settings().db_path
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _init(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS targets (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    title TEXT,
                    company TEXT,
                    linkedin_url TEXT,
                    email TEXT,
                    source TEXT,
                    status TEXT,
                    location TEXT,
                    headline TEXT,
                    already_contacted INTEGER NOT NULL DEFAULT 0,
                    blocked INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    url TEXT,
                    source TEXT,
                    location TEXT,
                    description TEXT,
                    score REAL,
                    discovered_at TEXT,
                    created_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS outreach (
                    id TEXT PRIMARY KEY,
                    target_id TEXT NOT NULL,
                    job_id TEXT,
                    channel TEXT NOT NULL,
                    subject TEXT,
                    message TEXT NOT NULL,
                    match_score REAL,
                    status TEXT NOT NULL,
                    created_at TEXT,
                    approved_at TEXT,
                    sent_at TEXT,
                    delivery_error TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approval_tokens (
                    token TEXT PRIMARY KEY,
                    outreach_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used INTEGER DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_messages (
                    message_id TEXT PRIMARY KEY,
                    processed_at TEXT NOT NULL
                )
                """
            )

            # Existing local databases are migrated in place so a project update
            # never requires deleting the user's history.
            migrations = {
                "targets": {
                    "location": "TEXT",
                    "headline": "TEXT",
                    "already_contacted": "INTEGER NOT NULL DEFAULT 0",
                    "blocked": "INTEGER NOT NULL DEFAULT 0",
                },
                "jobs": {
                    "location": "TEXT",
                    "description": "TEXT",
                    "discovered_at": "TEXT",
                },
                "outreach": {
                    "job_id": "TEXT",
                    "delivery_error": "TEXT",
                },
            }
            for table, columns in migrations.items():
                for column, definition in columns.items():
                    self._ensure_column(conn, table, column, definition)

    def add_audit_event(self, entity_type: str, entity_id: str, action: str, details: str = "") -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO audit_events (entity_type, entity_id, action, details, created_at) VALUES (?, ?, ?, ?, ?)",
                (entity_type, entity_id, action, details, self._now()),
            )

    def save_outreach(self, record: Dict[str, Any]) -> Dict[str, Any]:
        record = dict(record)
        outreach_id = record.get("id") or record.get("outreach_id")
        if outreach_id is None:
            raise ValueError("Outreach record requires an id or outreach_id")
        record["id"] = outreach_id
        if "outreach_id" not in record:
            record["outreach_id"] = outreach_id
        if "created_at" not in record:
            record["created_at"] = self._now()
        if "target_id" not in record:
            record["target_id"] = ""
        if "channel" not in record:
            record["channel"] = "email"
        if "subject" not in record:
            record["subject"] = ""
        if "message" not in record:
            record["message"] = ""
        if "status" not in record:
            record["status"] = "PENDING_APPROVAL"
        if "match_score" not in record:
            record["match_score"] = 0.0

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO outreach (id, target_id, job_id, channel, subject, message, match_score, status, created_at, approved_at, sent_at, delivery_error)
                VALUES (:id, :target_id, :job_id, :channel, :subject, :message, :match_score, :status, :created_at, :approved_at, :sent_at, :delivery_error)
                ON CONFLICT(id) DO UPDATE SET
                    target_id = excluded.target_id,
                    job_id = excluded.job_id,
                    channel = excluded.channel,
                    subject = excluded.subject,
                    message = excluded.message,
                    match_score = excluded.match_score,
                    status = excluded.status,
                    approved_at = excluded.approved_at,
                    sent_at = excluded.sent_at,
                    delivery_error = excluded.delivery_error
                """,
                {
                    **record,
                    "job_id": record.get("job_id"),
                    "approved_at": record.get("approved_at"),
                    "sent_at": record.get("sent_at"),
                    "delivery_error": record.get("delivery_error"),
                },
            )
        return self.get_outreach(outreach_id)

    def get_outreach(self, outreach_id: str) -> Dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM outreach WHERE id = ?",
                (outreach_id,),
            ).fetchone()
        if row is None:
            return {}
        data = dict(row)
        data["outreach_id"] = data.get("id", outreach_id)
        return data

    def create_approval_token(self, outreach_id: str, token: str | None = None) -> str:
        import secrets

        token = token or secrets.token_urlsafe(16)
        expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO approval_tokens (token, outreach_id, expires_at, used, status)
                VALUES (?, ?, ?, 0, 'PENDING_APPROVAL')
                ON CONFLICT(token) DO NOTHING
                """,
                (token, outreach_id, expires_at),
            )
        return token

    def get_active_approval_token(self, outreach_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT token FROM approval_tokens
                WHERE outreach_id = ? AND used = 0 AND status = 'PENDING_APPROVAL'
                ORDER BY expires_at DESC LIMIT 1
                """,
                (outreach_id,),
            ).fetchone()
        if row is None or not self.validate_approval_token(row["token"]):
            return None
        return str(row["token"])

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
                "UPDATE outreach SET status = 'APPROVED', approved_at = ? WHERE id = ? AND status = 'PENDING_APPROVAL'",
                (self._now(), outreach_id),
            )
            changed = conn.execute("SELECT changes() AS count").fetchone()["count"]
        if not changed:
            return False
        self.add_audit_event("outreach", outreach_id, "APPROVED")
        return True

    def reject_token(self, token: str) -> bool:
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
                "UPDATE approval_tokens SET used = 1, status = 'REJECTED' WHERE token = ?",
                (token,),
            )
            conn.execute(
                "UPDATE outreach SET status = 'REJECTED' WHERE id = ? AND status = 'PENDING_APPROVAL'",
                (outreach_id,),
            )
            changed = conn.execute("SELECT changes() AS count").fetchone()["count"]
        if not changed:
            return False
        self.add_audit_event("outreach", outreach_id, "REJECTED")
        return True

    def update_outreach_status(
        self,
        outreach_id: str,
        status: str,
        *,
        expected_status: str | None = None,
        delivery_error: str | None = None,
    ) -> bool:
        allowed = {"PENDING_APPROVAL", "APPROVED", "SENDING", "REJECTED", "SENT"}
        if status not in allowed:
            raise ValueError(f"Unsupported outreach status: {status}")
        fields = ["status = ?", "delivery_error = ?"]
        params: List[Any] = [status, delivery_error]
        if status == "APPROVED":
            fields.append("approved_at = ?")
            params.append(self._now())
        if status == "SENT":
            fields.append("sent_at = ?")
            params.append(self._now())
        query = f"UPDATE outreach SET {', '.join(fields)} WHERE id = ?"
        params.append(outreach_id)
        if expected_status:
            query += " AND status = ?"
            params.append(expected_status)
        with self._connect() as conn:
            conn.execute(query, params)
            changed = conn.execute("SELECT changes() AS count").fetchone()["count"]
        if changed:
            self.add_audit_event("outreach", outreach_id, status, delivery_error or "")
        return bool(changed)

    def count_sent_today(self) -> int:
        """Count how many outreach messages were sent today."""
        from datetime import datetime, timezone, timedelta

        today = datetime.now(timezone.utc).date()
        tomorrow = today + timedelta(days=1)
        today_start = f"{today}T00:00:00"
        today_end = f"{tomorrow}T00:00:00"

        with self._connect() as conn:
            result = conn.execute(
                "SELECT COUNT(*) as count FROM outreach WHERE status = 'SENT' AND sent_at >= ? AND sent_at < ?",
                (today_start, today_end),
            ).fetchone()

        return result["count"] if result else 0

    def get_sent_today(self) -> List[Dict[str, Any]]:
        """Get all outreach messages sent today."""
        from datetime import datetime, timezone, timedelta

        today = datetime.now(timezone.utc).date()
        tomorrow = today + timedelta(days=1)
        today_start = f"{today}T00:00:00"
        today_end = f"{tomorrow}T00:00:00"

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM outreach WHERE status = 'SENT' AND sent_at >= ? AND sent_at < ? ORDER BY sent_at",
                (today_start, today_end),
            ).fetchall()

        return [dict(row) for row in rows]

    def save_target(self, target: Dict[str, Any]) -> None:
        """Save a target profile."""
        target = dict(target)
        target_id = target.get("target_id") or target.get("id")
        if not target_id:
            raise ValueError("Target requires target_id or id")
        
        target["id"] = target_id
        if "created_at" not in target:
            target["created_at"] = self._now()
        
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO targets (id, name, title, company, linkedin_url, email, source, status, location, headline, already_contacted, blocked, created_at)
                VALUES (:id, :name, :title, :company, :linkedin_url, :email, :source, :status, :location, :headline, :already_contacted, :blocked, :created_at)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    title = excluded.title,
                    company = excluded.company,
                    linkedin_url = excluded.linkedin_url,
                    email = excluded.email,
                    source = excluded.source,
                    status = excluded.status,
                    location = excluded.location,
                    headline = excluded.headline,
                    already_contacted = excluded.already_contacted,
                    blocked = excluded.blocked
                """,
                {
                    "id": target_id,
                    "name": target.get("name", ""),
                    "title": target.get("title", ""),
                    "company": target.get("company", ""),
                    "linkedin_url": target.get("linkedin_url"),
                    "email": target.get("email"),
                    "source": target.get("source", "manual"),
                    "status": target.get("status", "DISCOVERED"),
                    "location": target.get("location"),
                    "headline": target.get("headline"),
                    "already_contacted": int(bool(target.get("already_contacted", False))),
                    "blocked": int(bool(target.get("blocked", False))),
                    "created_at": target.get("created_at"),
                },
            )

    def get_target(self, target_id: str) -> Dict[str, Any]:
        """Get a target by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM targets WHERE id = ?", (target_id,)).fetchone()
        if not row:
            return {}
        data = dict(row)
        data["already_contacted"] = bool(data.get("already_contacted"))
        data["blocked"] = bool(data.get("blocked"))
        return data

    def list_targets(self, status: str | None = None) -> List[Dict[str, Any]]:
        """List all targets, optionally filtered by status."""
        query = "SELECT * FROM targets"
        params: List[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["already_contacted"] = bool(item.get("already_contacted"))
            item["blocked"] = bool(item.get("blocked"))
            result.append(item)
        return result

    def mark_target_contacted(self, target_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE targets SET already_contacted = 1, status = 'CONTACTED' WHERE id = ?",
                (target_id,),
            )

    def save_job(self, job: Dict[str, Any]) -> None:
        """Save a job posting."""
        job = dict(job)
        job_id = job.get("job_id") or job.get("id")
        if not job_id:
            raise ValueError("Job requires job_id or id")
        
        job["id"] = job_id
        if "created_at" not in job:
            job["created_at"] = self._now()
        
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, title, company, url, source, location, description, score, discovered_at, created_at)
                VALUES (:id, :title, :company, :url, :source, :location, :description, :score, :discovered_at, :created_at)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    company = excluded.company,
                    url = excluded.url,
                    source = excluded.source,
                    location = excluded.location,
                    description = excluded.description,
                    score = excluded.score,
                    discovered_at = excluded.discovered_at
                """,
                {
                    "id": job_id,
                    "title": job.get("title", ""),
                    "company": job.get("company", ""),
                    "url": job.get("url"),
                    "source": job.get("source", "manual"),
                    "location": job.get("location"),
                    "description": job.get("description"),
                    "score": job.get("score"),
                    "discovered_at": job.get("discovered_at"),
                    "created_at": job.get("created_at"),
                },
            )

    def get_job(self, job_id: str) -> Dict[str, Any]:
        """Get a job by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else {}

    def list_jobs(self) -> List[Dict[str, Any]]:
        """List all jobs."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def list_outreach(self, status: str | None = None) -> List[Dict[str, Any]]:
        """List all outreach records, optionally filtered by status."""
        query = "SELECT * FROM outreach"
        params: List[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"
        
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def has_active_outreach(self, target_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM outreach WHERE target_id = ? AND status IN ('PENDING_APPROVAL', 'APPROVED', 'SENDING', 'SENT') LIMIT 1",
                (target_id,),
            ).fetchone()
        return row is not None

    def email_already_contacted(self, email: str, exclude_target_id: str | None = None) -> bool:
        """True if any other target with this email was contacted or has active outreach."""
        email = (email or "").strip().lower()
        if not email:
            return False
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM targets t
                WHERE lower(t.email) = ? AND t.id != ? AND (
                    t.already_contacted = 1 OR t.blocked = 1 OR EXISTS (
                        SELECT 1 FROM outreach o WHERE o.target_id = t.id
                        AND o.status IN ('PENDING_APPROVAL', 'APPROVED', 'SENDING', 'SENT')
                    )
                ) LIMIT 1
                """,
                (email, exclude_target_id or ""),
            ).fetchone()
        return row is not None

    def list_audit_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT entity_type, entity_id, action, details, created_at FROM audit_events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def outreach_id_for_token(self, token: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT outreach_id FROM approval_tokens WHERE token = ?", (token,)).fetchone()
        return str(row["outreach_id"]) if row else None

    def claim_message(self, message_id: str) -> bool:
        """Record a Gmail message as processed. False if it was already processed."""
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO processed_messages (message_id, processed_at) VALUES (?, ?)",
                (message_id, self._now()),
            )
            return conn.execute("SELECT changes() AS count").fetchone()["count"] == 1

    def status_counts(self) -> Dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT status, COUNT(*) AS count FROM outreach GROUP BY status").fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}
