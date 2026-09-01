from __future__ import annotations

import re
from typing import Any, Dict, List

from app.storage import ReachAIStore


class ApprovalWorker:
    def __init__(self, store: ReachAIStore | None = None):
        self.store = store or ReachAIStore()

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
    def __init__(self, store: ReachAIStore | None = None):
        self.store = store or ReachAIStore()

    def process_pending(self) -> List[Dict[str, str]]:
        result: List[Dict[str, str]] = []
        with self.store._connect() as conn:
            rows = conn.execute(
                "SELECT outreach_id, status, message FROM outreach WHERE status = 'APPROVED' ORDER BY created_at"
            ).fetchall()

        for row in rows:
            outreach_id = row["outreach_id"]
            self.store.save_outreach({
                "outreach_id": outreach_id,
                "target_name": "",
                "company": "",
                "status": "SENT",
                "message": row["message"],
            })
            result.append({"outreach_id": outreach_id, "status": "SENT"})
        return result
