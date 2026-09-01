from __future__ import annotations

from typing import Any, Dict

from app.models import CandidateProfile, TargetProfile
from app.service import ApprovalSkill, EligibilitySkill, OutreachWorkflow, PersonalizationSkill, ProfileSkill, ScoringSkill, SendSkill, TargetDiscoverySkill


class LocalReachAI:
    def __init__(self):
        self.profile_skill = ProfileSkill()
        self.target_discovery_skill = TargetDiscoverySkill()
        self.eligibility_skill = EligibilitySkill()
        self.scoring_skill = ScoringSkill()
        self.personalization_skill = PersonalizationSkill()
        self.approval_skill = ApprovalSkill()
        self.send_skill = SendSkill()
        self.workflow = OutreachWorkflow()

    def run(self, candidate: CandidateProfile, target: TargetProfile) -> Dict[str, Any]:
        profile = self.profile_skill.load_profile(candidate)
        normalized = self.target_discovery_skill.normalize_target(target)

        if not self.eligibility_skill.is_eligible(profile, normalized):
            return {
                "eligible": False,
                "reason": "Target failed eligibility checks.",
                "score": 0,
            }

        score = self.scoring_skill.score(profile, normalized)
        if score < 75:
            return {
                "eligible": False,
                "reason": "Target score below minimum threshold.",
                "score": score,
            }

        research_summary = (
            f"{normalized.name} is a {normalized.role} at {normalized.company}. "
            f"This contact is relevant because the target role sits in a hiring context that matches "
            f"Aman's background in {', '.join(profile.experience[:2])} and skills in {', '.join(profile.skills[:3])}."
        )

        draft_text = self.personalization_skill.draft(profile, normalized, research_summary, score)
        critique = self.workflow.critic_agent.review(draft_text, {
            "company": normalized.company,
            "target_person": normalized.name,
            "role": normalized.role,
        })

        if critique["status"] == "fail":
            return {
                "eligible": True,
                "score": score,
                "draft": {
                    "message": draft_text,
                    "needs_approval": True,
                    "status": "PENDING_APPROVAL",
                },
                "critique": critique,
            }

        approval = self.approval_skill.prepare_for_review(
            draft_text,
            outreach_id=f"draft-{normalized.target_id or normalized.name.lower().replace(' ', '-')}",
        )
        return {
            "eligible": True,
            "score": score,
            "research_summary": research_summary,
            "draft": {
                "message": draft_text,
                "needs_approval": approval["needs_approval"],
                "status": approval["status"],
                "approval_token": approval["approval_token"],
            },
            "critique": critique,
        }
