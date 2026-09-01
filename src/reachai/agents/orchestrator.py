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

    def run(self, candidate: CandidateProfile, target: TargetProfile) -> Dict[str, Any]:
        job = {"title": "AI Engineer", "description": "Python, LLM workflows, AI agents, RAG", "score": 90}
        eligible, reason = self.eligibility_skill.check({
            "title": target.title or target.name,
            "company": target.company,
            "blocked": target.blocked,
            "already_contacted": target.already_contacted,
        }, job)

        if not eligible:
            return {"eligible": False, "reason": reason}

        score = self.scoring_skill.score_target(25, 20, 20, 20, 10, 5)
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
            "draft": draft,
            "critic": critic,
            "approval_token": token,
            "approval_email": approval_email,
        }
