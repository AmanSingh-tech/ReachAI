from __future__ import annotations

from typing import Any, Dict, Tuple


class EligibilitySkill:
    def __init__(self):
        self.allowed_titles = {
            "recruiter",
            "technical recruiter",
            "talent acquisition",
            "hiring manager",
            "engineering manager",
            "head of engineering",
            "founder",
        }

    def check(self, target: Dict[str, Any], job: Dict[str, Any] | None = None, history: list[str] | None = None) -> Tuple[bool, str]:
        title = str(target.get("title", target.get("role", "")).lower())
        if target.get("blocked"):
            return False, "blocked"
        if target.get("already_contacted"):
            return False, "already_contacted"
        if not any(keyword in title for keyword in self.allowed_titles):
            return False, "role_not_targeted"
        if job and job.get("score") is not None and float(job.get("score", 0)) < 75:
            return False, "job_score_too_low"
        return True, "eligible"
