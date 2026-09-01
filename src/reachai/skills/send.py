from __future__ import annotations

from typing import Any, Dict


class SendSkill:
    def send(self, outreach: Dict[str, Any]) -> Dict[str, str]:
        if outreach.get("status") != "APPROVED":
            raise PermissionError("Outreach has not been explicitly approved.")
        return {"status": "QUEUED", "channel": outreach.get("channel", "email"), "message": outreach.get("message", "")}
