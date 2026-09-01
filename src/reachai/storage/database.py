import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List


class Database:
    def __init__(self, db_path: str = "data/reachai.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

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
                    score REAL,
                    created_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS outreach (
                    id TEXT PRIMARY KEY,
                    target_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    subject TEXT,
                    message TEXT NOT NULL,
                    match_score REAL,
                    status TEXT NOT NULL,
                    created_at TEXT,
                    approved_at TEXT,
                    sent_at TEXT
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

    def save_outreach(self, record: Dict[str, Any]) -> Dict[str, Any]:
        record = dict(record)
        outreach_id = record.get("id") or record.get("outreach_id")
        if outreach_id is None:
            raise ValueError("Outreach record requires an id or outreach_id")
        record["id"] = outreach_id
        if "outreach_id" not in record:
            record["outreach_id"] = outreach_id
        if "created_at" not in record:
            record["created_at"] = datetime.now(timezone.utc).isoformat()
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
                INSERT INTO outreach (id, target_id, channel, subject, message, match_score, status, created_at, approved_at, sent_at)
                VALUES (:id, :target_id, :channel, :subject, :message, :match_score, :status, :created_at, :approved_at, :sent_at)
                ON CONFLICT(id) DO UPDATE SET
                    target_id = excluded.target_id,
                    channel = excluded.channel,
                    subject = excluded.subject,
                    message = excluded.message,
                    match_score = excluded.match_score,
                    status = excluded.status,
                    approved_at = excluded.approved_at,
                    sent_at = excluded.sent_at
                """,
                {
                    **record,
                    "approved_at": record.get("approved_at"),
                    "sent_at": record.get("sent_at"),
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

    def create_approval_token(self, outreach_id: str) -> str:
        import secrets

        token = secrets.token_urlsafe(16)
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
                "UPDATE outreach SET status = 'APPROVED' WHERE id = ?",
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
                "UPDATE outreach SET status = 'REJECTED' WHERE id = ?",
                (outreach_id,),
            )
        return True

    def count_sent_today(self) -> int:
        """Count how many outreach messages were sent today."""
        from datetime import datetime, timezone, timedelta

        today = datetime.now(timezone.utc).date()
        tomorrow = today + timedelta(days=1)
        today_start = f"{today}T00:00:00"
        today_end = f"{tomorrow}T00:00:00"

        with self._connect() as conn:
            result = conn.execute(
                "SELECT COUNT(*) as count FROM outreach WHERE status = 'SENT' AND created_at >= ? AND created_at < ?",
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
                "SELECT * FROM outreach WHERE status = 'SENT' AND created_at >= ? AND created_at < ? ORDER BY created_at",
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
            target["created_at"] = datetime.now(timezone.utc).isoformat()
        
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO targets (id, name, title, company, linkedin_url, email, source, status, created_at)
                VALUES (:id, :name, :title, :company, :linkedin_url, :email, :source, :status, :created_at)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    title = excluded.title,
                    company = excluded.company,
                    linkedin_url = excluded.linkedin_url,
                    email = excluded.email,
                    source = excluded.source,
                    status = excluded.status
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
                    "created_at": target.get("created_at"),
                },
            )

    def get_target(self, target_id: str) -> Dict[str, Any]:
        """Get a target by ID."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM targets WHERE id = ?", (target_id,)).fetchone()
        return dict(row) if row else {}

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
        return [dict(row) for row in rows]

    def save_job(self, job: Dict[str, Any]) -> None:
        """Save a job posting."""
        job = dict(job)
        job_id = job.get("job_id") or job.get("id")
        if not job_id:
            raise ValueError("Job requires job_id or id")
        
        job["id"] = job_id
        if "created_at" not in job:
            job["created_at"] = datetime.now(timezone.utc).isoformat()
        
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jobs (id, title, company, url, source, score, created_at)
                VALUES (:id, :title, :company, :url, :source, :score, :created_at)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    company = excluded.company,
                    url = excluded.url,
                    source = excluded.source,
                    score = excluded.score
                """,
                {
                    "id": job_id,
                    "title": job.get("title", ""),
                    "company": job.get("company", ""),
                    "url": job.get("url"),
                    "source": job.get("source", "manual"),
                    "score": job.get("score"),
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

