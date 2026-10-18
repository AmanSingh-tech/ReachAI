from __future__ import annotations

from typing import Any, Dict, List


def _join(items: List[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


class PersonalizationSkill:
    def generate(self, candidate: Dict[str, Any], target: Dict[str, Any], job: Dict[str, Any] | None = None, research: Dict[str, Any] | None = None, match_score: float | None = None) -> Dict[str, Any]:
        first_name = str(target.get("name", "")).split()[0]
        company = str(target.get("company", "")).strip()
        resume_url = str(candidate.get("resume_url", "")).strip()
        job = job or {}
        job_title = str(job.get("title", "AI Engineer")).strip() or "AI Engineer"

        # Only facts from the candidate profile are used; nothing is inferred.
        experience = [str(item).strip() for item in candidate.get("experience", []) if str(item).strip()][:2]
        skills = [str(item).strip() for item in candidate.get("skills", []) if str(item).strip()]
        job_text = f"{job_title} {job.get('description') or ''}".lower()
        matched_skills = [skill for skill in skills if skill.lower().rstrip("s") in job_text][:3] or skills[:3]

        background = []
        if matched_skills:
            background.append(f"I work with {_join(matched_skills)}.")
        if experience:
            noun = "role" if len(experience) == 1 else "roles"
            background.append(f"My experience includes the {_join(experience)} {noun}.")
        background_line = " ".join(background) or "My background is in AI and product engineering."

        summary = (
            f"Hi {first_name},\n\n"
            f"I came across the {job_title} opening at {company}. {background_line} "
            f"I’d value the chance to learn more about the team. "
            f"Here is my resume: {resume_url}\n\n"
            f"Thanks,\n{candidate.get('name', 'Aman Singh')}"
        )
        return {
            "should_contact": True,
            "channel": "email",
            "subject": f"Interest in the {job_title} role",
            "message": summary,
            "personalization_points": [
                f"Recorded {job_title} role at {company}",
                f"Candidate experience: {_join(experience) or 'not listed'}",
                f"Relevant skills: {_join(matched_skills) or 'not listed'}",
            ],
            "confidence": 0.92,
        }
