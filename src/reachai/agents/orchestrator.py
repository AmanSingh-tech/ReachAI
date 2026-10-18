from __future__ import annotations

from typing import Any, Dict, List

from reachai.models.candidate import CandidateProfile
from reachai.models.target import TargetProfile
from reachai.skills.eligibility import EligibilitySkill
from reachai.skills.personalization import PersonalizationSkill
from reachai.skills.scoring import ScoringSkill
from reachai.skills.research import ResearchSkill
from reachai.skills.critic import CriticSkill
from reachai.skills.approval import ApprovalSkill


class ReachAIOrchestrator:
    def __init__(self):
        self.eligibility_skill = EligibilitySkill()
        self.scoring_skill = ScoringSkill()
        self.research_skill = ResearchSkill()
        self.personalization_skill = PersonalizationSkill()
        self.critic_skill = CriticSkill()
        self.approval_skill = ApprovalSkill()

    def run(
        self,
        candidate: CandidateProfile,
        target: TargetProfile,
        job: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        job = job or {
            "title": candidate.target_roles[0] if candidate.target_roles else "AI Engineer",
            "company": target.company,
            "description": "",
            "score": 90,
        }
        if job.get("score") is None:
            job = dict(job)
            job["score"] = self.scoring_skill.score_job(job, candidate.model_dump())
        eligible, reason = self.eligibility_skill.check({
            "title": target.title or target.name,
            "company": target.company,
            "blocked": target.blocked,
            "already_contacted": target.already_contacted,
        }, job)

        if not eligible:
            return {"eligible": False, "reason": reason}

        role_title = target.title.lower()
        role_relevance = 25 if any(
            term in role_title
            for term in ("recruiter", "talent", "hiring manager", "engineering manager", "head of engineering", "founder")
        ) else 0
        same_company = str(job.get("company", "")).strip().lower() == target.company.strip().lower()
        company_relevance = 20 if same_company else 5
        job_score = float(job.get("score", 0))
        hiring_signal = 20 if job_score >= 75 else 10 if job_score >= 50 else 0
        skills_overlap = min(int(job_score * 0.2), 20)
        seniority = 10 if any(term in role_title for term in ("manager", "head", "founder")) else 5
        research_confidence = 5 if target.company and target.title else 0
        score = self.scoring_skill.score_target(
            role_relevance,
            company_relevance,
            hiring_signal,
            skills_overlap,
            seniority,
            research_confidence,
        )
        research = self.research_skill.run(candidate.model_dump(), target.model_dump(), job)
        draft = self.personalization_skill.generate(candidate.model_dump(), target.model_dump(), job, research, score)
        critic = self.critic_skill.review(draft, {"company": target.company})

        if not critic["passed"]:
            return {"eligible": True, "score": score, "draft": draft, "critic": critic}

        token = self.approval_skill.create_token(f"outreach-{target.target_id or target.name.lower().replace(' ', '-')}")
        approval_email = self.approval_skill.build_review_email(
            target_name=target.name,
            company=target.company,
            score=score,
            message=draft["message"],
            approval_token=token,
        )

        return {
            "eligible": True,
            "score": score,
            "research": research,
            "draft": draft,
            "critic": critic,
            "approval_token": token,
            "approval_email": approval_email,
        }
