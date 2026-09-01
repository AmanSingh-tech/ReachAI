from __future__ import annotations

import re
from typing import Any, Dict, List

from reachai.storage.database import Database


class ApprovalWorker:
    def __init__(self, store: Database | None = None):
        self.store = store or Database()

    def process_email(self, email: Dict[str, Any]) -> Dict[str, str]:
        body = str(email.get("body", "")).strip()
        match = re.search(r"\b(APPROVE|REJECT)\s+([A-Za-z0-9_-]+)", body, re.IGNORECASE)
        if not match:
            return {"action": "NO_ACTION", "reason": "No valid approval command found."}

        action = match.group(1).upper()
        token = match.group(2)

        if action == "APPROVE":
            if self.store.approve_token(token):
                return {"action": "APPROVED", "token": token}
            return {"action": "REJECTED", "token": token, "reason": "Approval token was invalid or already used."}

        if self.store.reject_token(token):
            return {"action": "REJECTED", "token": token}
        return {"action": "REJECTED", "token": token, "reason": "Reject token was invalid or already used."}


class SendWorker:
    def __init__(self, store: Database | None = None):
        self.store = store or Database()

    def process_pending(self) -> List[Dict[str, str]]:
        result: List[Dict[str, str]] = []
        with self.store._connect() as conn:
            rows = conn.execute(
                "SELECT id as outreach_id, status, message FROM outreach WHERE status = 'APPROVED' ORDER BY created_at"
            ).fetchall()

        for row in rows:
            outreach_id = row["outreach_id"]
            self.store.save_outreach({
                "id": outreach_id,
                "target_id": "",
                "channel": "email",
                "subject": "",
                "status": "SENT",
                "message": row["message"],
                "match_score": 0.0,
            })
            result.append({"outreach_id": outreach_id, "status": "SENT"})
        return result
