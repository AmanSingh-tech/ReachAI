from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class OutreachRecord(BaseModel):
    outreach_id: str
    target_id: str
    channel: str
    message: str
    subject: Optional[str] = None
    match_score: float
    status: str = "PENDING_APPROVAL"
    approval_token: Optional[str] = None
    critic_passed: bool = False
    created_at: str
    approved_at: Optional[str] = None
    sent_at: Optional[str] = None
