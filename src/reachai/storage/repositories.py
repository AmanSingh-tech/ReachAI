from __future__ import annotations

from typing import Any, Dict, List

from reachai.storage.database import Database


class Repository:
    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    def save_target(self, target: Dict[str, Any]) -> None:
        with self.db._connect() as conn:
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
                target,
            )

    def save_outreach(self, outreach: Dict[str, Any]) -> None:
        with self.db._connect() as conn:
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
                outreach,
            )

    def list_outreach(self, status: str | None = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM outreach"
        params: List[Any] = []
        if status is not None:
            query += " WHERE status = ?"
            params.append(status)
        with self.db._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
