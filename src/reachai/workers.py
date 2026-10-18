from __future__ import annotations

import re
from email.utils import parseaddr
from typing import Any, Dict, List

from reachai.config import get_settings
from reachai.integrations.gmail import GmailClient
from reachai.storage.database import Database


_QUOTE_START = re.compile(r"^(>|On .+wrote:?$|-+\s*Original Message|From:\s)", re.IGNORECASE)
_COMMAND = re.compile(r"^\s*(APPROVE|APPROVED|REJECT|REJECTED)\b[\s:]*([A-Za-z0-9_-]{8,})?", re.IGNORECASE)
_SUBJECT_REF = re.compile(r"\bref[:\s]+([A-Za-z0-9_-]{8,})", re.IGNORECASE)


def _reply_text(body: str) -> str:
    """The text the sender typed, without the quoted original email."""
    lines = []
    for line in body.replace("\r\n", "\n").split("\n"):
        if _QUOTE_START.match(line.strip()):
            break
        lines.append(line)
    return "\n".join(lines)


class ApprovalWorker:
    def __init__(self, store: Database | None = None, owner_email: str | None = None):
        self.store = store or Database()
        # When set, only replies sent from this address can approve or reject.
        self.owner_email = (owner_email or "").strip().lower()

    def process_email(self, email: Dict[str, Any]) -> Dict[str, str]:
        if self.owner_email:
            sender = parseaddr(str(email.get("from", "")))[1].lower()
            if sender != self.owner_email:
                return {"action": "NO_ACTION", "reason": "Reply was not sent by the owner."}

        # Only the first non-empty line of the typed reply counts, so quoted
        # instructions in the original approval email can never trigger an action.
        typed = [line for line in _reply_text(str(email.get("body", ""))).split("\n") if line.strip()]
        match = _COMMAND.match(typed[0]) if typed else None
        if not match:
            return {"action": "NO_ACTION", "reason": "No valid approval command found."}

        action = "APPROVE" if match.group(1).upper().startswith("APPROVE") else "REJECT"
        token = match.group(2)
        if not token:
            ref = _SUBJECT_REF.search(str(email.get("subject", "")))
            token = ref.group(1) if ref else None
        if not token:
            return {"action": "NO_ACTION", "reason": "Reply did not identify which draft it refers to."}

        if action == "APPROVE":
            if self.store.approve_token(token):
                return {"action": "APPROVED", "token": token}
            return {"action": "REJECTED", "token": token, "reason": "Approval token was invalid or already used."}

        if self.store.reject_token(token):
            return {"action": "REJECTED", "token": token}
        return {"action": "REJECTED", "token": token, "reason": "Reject token was invalid or already used."}


class SendWorker:
    def __init__(
        self,
        store: Database | None = None,
        gmail_client: GmailClient | None = None,
        send_mode: str | None = None,
        daily_limit: int | None = None,
    ):
        settings = get_settings()
        self.store = store or Database()
        self.gmail_client = gmail_client or GmailClient()
        self.send_mode = (send_mode or settings.send_mode).lower()
        self.daily_limit = daily_limit if daily_limit is not None else settings.daily_limit

    def process_pending(self) -> List[Dict[str, str]]:
        result: List[Dict[str, str]] = []
        with self.store._connect() as conn:
            rows = conn.execute(
                "SELECT id AS outreach_id FROM outreach WHERE status = 'APPROVED' ORDER BY approved_at, created_at"
            ).fetchall()

        for row in rows:
            if self.store.count_sent_today() >= self.daily_limit:
                break
            send_result = self.process_one(str(row["outreach_id"]))
            if send_result.get("status") == "SENT":
                result.append({"outreach_id": str(row["outreach_id"]), "status": "SENT"})
        return result

    def process_one(self, outreach_id: str) -> Dict[str, str]:
        with self.store._connect() as conn:
            row = conn.execute(
                """
                SELECT o.id AS outreach_id, o.target_id, o.status, o.subject, o.message,
                       t.email AS recipient, t.blocked, t.already_contacted
                FROM outreach o
                LEFT JOIN targets t ON t.id = o.target_id
                WHERE o.id = ?
                """,
                (outreach_id,),
            ).fetchone()
        if row is None:
            return {"outreach_id": outreach_id, "status": "NOT_FOUND"}
        if row["status"] != "APPROVED":
            return {"outreach_id": outreach_id, "status": "NOT_APPROVED"}
        if row["blocked"] or row["already_contacted"]:
            return {"outreach_id": outreach_id, "status": "FAILED", "error": "Target is blocked or was already contacted."}
        if self.store.count_sent_today() >= self.daily_limit:
            return {"outreach_id": outreach_id, "status": "DAILY_LIMIT", "error": "Daily outreach limit reached; it will be sent on a later day."}
        if self.send_mode not in {"dry-run", "gmail"}:
            return {"outreach_id": outreach_id, "status": "FAILED", "error": f"Unsupported send mode: {self.send_mode}"}

        recipient = str(row["recipient"] or "").strip()
        if self.send_mode == "gmail" and not recipient:
            return {"outreach_id": outreach_id, "status": "FAILED", "error": "Target email is missing."}

        # Claim the row first so two processes can never send the same message.
        if not self.store.update_outreach_status(outreach_id, "SENDING", expected_status="APPROVED"):
            return {"outreach_id": outreach_id, "status": "FAILED", "error": "Outreach state changed before delivery."}

        if self.send_mode == "gmail":
            provider_result = self.gmail_client.send_outreach(
                recipient=recipient,
                subject=str(row["subject"] or "ReachAI outreach"),
                body=str(row["message"]),
            )
            if provider_result.get("status") != "sent":
                error = f"Gmail did not confirm delivery: {provider_result.get('error', 'unknown error')}"
                self.store.update_outreach_status(outreach_id, "APPROVED", expected_status="SENDING", delivery_error=error)
                return {"outreach_id": outreach_id, "status": "FAILED", "error": error}

        self.store.update_outreach_status(outreach_id, "SENT", expected_status="SENDING")
        if row["target_id"]:
            self.store.mark_target_contacted(str(row["target_id"]))
        return {"outreach_id": outreach_id, "status": "SENT"}
