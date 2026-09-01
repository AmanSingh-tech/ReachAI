from __future__ import annotations

from typing import Any, Dict


class PersonalizationSkill:
    def generate(self, candidate: Dict[str, Any], target: Dict[str, Any], job: Dict[str, Any] | None = None, research: Dict[str, Any] | None = None, match_score: float | None = None) -> Dict[str, Any]:
        first_name = str(target.get("name", "")).split()[0]
        company = str(target.get("company", "")).strip()
        resume_url = str(candidate.get("resume_url", "https://example.com/resume")).strip()
        summary = (
            f"Hi {first_name},\n\n"
            f"I noticed you're hiring for AI and product-focused work at {company}, and my background in "
            f"{', '.join(candidate.get('experience', [])[:2])} aligns closely with what your team is building. "
            f"I’d love to connect and share my resume: {resume_url}.\n\n"
            f"Thanks,\n{candidate.get('name', 'Aman Singh')}"
        )
        return {
            "should_contact": True,
            "channel": "email",
            "subject": f"AI Engineer opportunity",
            "message": summary,
            "personalization_points": [
                f"Relevant role at {company}",
                "Background aligns with AI product work",
            ],
            "confidence": 0.92,
        }
