from __future__ import annotations

from typing import Any, Dict


class ScoringSkill:
    def score_job(self, job: Dict[str, Any], candidate: Dict[str, Any]) -> float:
        score = 0.0
        title = str(job.get("title", "")).lower()
        description = str(job.get("description", "")).lower()
        skill_text = " ".join(candidate.get("skills", []) + candidate.get("strengths", [])).lower()

        if any(str(role).strip().lower() in title for role in candidate.get("target_roles", []) if str(role).strip()):
            score += 65
        if "ai engineer" in title:
            score += 30
        if "machine learning" in title or "ml engineer" in title:
            score += 25
        if "llm" in description:
            score += 15
        if "python" in description:
            score += 10
        if "rag" in description:
            score += 10
        if "agent" in description:
            score += 10
        if any(term in skill_text for term in ["llm", "rag", "agent", "python", "ai"]):
            score += 10
        return min(score, 100)

    def score_target(self, role_relevance: int, company_relevance: int, hiring_signal: int, skills_overlap: int, seniority: int, research_confidence: int) -> int:
        return min(role_relevance + company_relevance + hiring_signal + skills_overlap + seniority + research_confidence, 100)
