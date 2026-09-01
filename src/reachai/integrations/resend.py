from __future__ import annotations

from typing import Any, Dict


class ResendClient:
    def send_email(self, to: str, subject: str, body: str) -> Dict[str, Any]:
        return {"status": "queued", "to": to, "subject": subject}
