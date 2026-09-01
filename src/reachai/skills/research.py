from __future__ import annotations

from typing import Any, Dict, List


class ResearchSkill:
    def run(self, candidate: Dict[str, Any], target: Dict[str, Any], job: Dict[str, Any] | None = None) -> Dict[str, Any]:
        company = str(target.get("company", "")).strip()
        role = str(target.get("title", target.get("role", ""))).strip()
        skills = ", ".join(candidate.get("skills", [])[:3])
        return {
            "company_summary": f"{company} is a company working in product and AI delivery.",
            "role_summary": f"{role} is a relevant hiring role for this candidate profile.",
            "hiring_signal": "Hiring signal appears present because the role is in AI or platform work.",
            "relevant_fact": f"The target is connected to AI-focused hiring, and the candidate has relevant skills in {skills}.",
            "evidence": [
                {"fact": f"Target role is {role}", "source": "target_record", "confidence": 0.9},
                {"fact": f"Company is {company}", "source": "company_record", "confidence": 0.8},
            ],
            "confidence": 0.91,
        }
