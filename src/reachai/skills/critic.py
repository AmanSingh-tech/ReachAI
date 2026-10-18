from __future__ import annotations

from typing import Any, Dict, List


class CriticSkill:
    def review(self, draft: Dict[str, Any], context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        message = str(draft.get("message", ""))
        lower = message.lower()
        issues: List[str] = []

        if "http" not in lower:
            issues.append("missing_resume_link")
        company = str((context or {}).get("company", "")).strip().lower()
        if company and company not in lower:
            issues.append("not_personalized")
        if len(message) > 500:
            issues.append("too_long")
        if any(token in lower for token in ["dear", "i hope this email finds you well"]):
            issues.append("spammy")

        if issues:
            return {"passed": False, "issues": issues, "confidence": 0.9}
        return {"passed": True, "issues": [], "confidence": 0.96}
