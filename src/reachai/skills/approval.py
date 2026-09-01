from __future__ import annotations

import secrets
from typing import Any, Dict


class ApprovalSkill:
    def __init__(self):
        self.tokens: Dict[str, Dict[str, Any]] = {}

    def create_token(self, outreach_id: str) -> str:
        token = secrets.token_urlsafe(16)
        self.tokens[token] = {"outreach_id": outreach_id, "status": "PENDING_APPROVAL", "used": False}
        return token

    def validate_token(self, token: str) -> bool:
        record = self.tokens.get(token)
        return bool(record and not record["used"])

    def approve(self, token: str) -> bool:
        record = self.tokens.get(token)
        if not record or record["used"]:
            return False
        record["used"] = True
        record["status"] = "APPROVED"
        return True

    def reject(self, token: str) -> bool:
        record = self.tokens.get(token)
        if not record or record["used"]:
            return False
        record["used"] = True
        record["status"] = "REJECTED"
        return True

    def build_review_email(self, target_name: str, company: str, score: int, message: str, approval_token: str) -> Dict[str, str]:
        approve_url = f"https://example.com/approval/{approval_token}/approve"
        reject_url = f"https://example.com/approval/{approval_token}/reject"
        subject = f"[ReachAI] Approval required — {target_name}"
        body = (
            f"ReachAI outreach review\n\n"
            f"Target: {target_name}\n"
            f"Company: {company}\n"
            f"Score: {score}/100\n\n"
            f"Draft:\n{message}\n\n"
            f"Choose an action:\n"
            f"Approve: {approve_url}\n"
            f"Reject: {reject_url}"
        )
        return {"subject": subject, "body": body, "approve_url": approve_url, "reject_url": reject_url}
