from __future__ import annotations

from typing import Any, Dict, List


class ResearchSkill:
    def run(self, candidate: Dict[str, Any], target: Dict[str, Any], job: Dict[str, Any] | None = None) -> Dict[str, Any]:
        company = str(target.get("company", "")).strip()
        role = str(target.get("title", target.get("role", ""))).strip()
        skills = ", ".join(candidate.get("skills", [])[:3])
        job = job or {}
        job_title = str(job.get("title", "")).strip()
        job_description = str(job.get("description", "")).strip()
        company_match = str(job.get("company", "")).strip().lower() == company.lower()
        source = str(job.get("source", "local_record"))
        company_summary = (
            f"{company} has a recorded opening for {job_title}."
            if company_match and job_title
            else f"The supplied target record associates {role} with {company}."
        )
        hiring_signal = (
            f"A {job_title} opening is present in the local job records."
            if job_title
            else "No separate job opening was supplied; only the target record is available."
        )
        return {
            "company_summary": company_summary,
            "role_summary": f"The target record lists {role} as {target.get('name', 'the contact')}'s role.",
            "hiring_signal": hiring_signal,
            "relevant_fact": f"The candidate profile lists relevant skills in {skills}.",
            "evidence": [
                {"fact": f"Target role is {role}", "source": "target_record", "confidence": 0.9},
                {"fact": f"Company is {company}", "source": "target_record", "confidence": 0.9},
                *([{
                    "fact": f"Recorded opening is {job_title}: {job_description[:160]}",
                    "source": source,
                    "confidence": 0.9,
                }] if job_title else []),
            ],
            "confidence": 0.9 if job_title else 0.75,
        }
