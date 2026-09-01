from __future__ import annotations

import secrets
from typing import Any, Dict, List

from app.config import get_settings
from app.models import CandidateProfile, OutreachDraft, OutreachRequest, TargetProfile
from app.storage import ReachAIStore


class ProfileSkill:
    def load_profile(self, candidate: CandidateProfile) -> CandidateProfile:
        return candidate


class TargetDiscoverySkill:
    def normalize_target(self, target: TargetProfile) -> TargetProfile:
        target.target_id = target.target_id or f"target-{target.name.lower().replace(' ', '-')}-{target.company.lower().replace(' ', '-')}"
        return target


class EligibilitySkill:
    def is_eligible(self, candidate: CandidateProfile, target: TargetProfile) -> bool:
        role = (target.role or "").lower()
        candidate_roles = [item.lower() for item in candidate.target_roles]

        relevant_role = any(term in role for term in [
            "recruiter",
            "hiring manager",
            "engineering manager",
            "founder",
            "talent",
            "technical recruiter",
        ])
        role_match = any(term in role for term in ["recruiter", "manager"]) or any(term in role for term in candidate_roles)

        if not relevant_role and not role_match:
            return False

        return True


class ScoringSkill:
    def score(self, candidate: CandidateProfile, target: TargetProfile) -> int:
        score = 40
        role = (target.role or "").lower()
        company = (target.company or "").lower()
        skills_text = " ".join(candidate.skills + candidate.strengths + candidate.experience).lower()

        if any(term in role for term in ["hiring manager", "recruiter", "engineering manager", "technical recruiter", "founder"]):
            score += 20
        if any(term in company for term in ["ai", "ml", "llm", "agent", "data", "lab", "platform"]):
            score += 10
        if any(term in skills_text for term in ["llm", "agent", "ai", "ml", "python", "next.js", "node.js"]):
            score += 15
        if any(role_term in role for role_term in [term.lower() for term in candidate.target_roles]):
            score += 10
        if any(term in skills_text for term in ["rag", "prompt", "workflow", "mlops", "openai", "gemini"]):
            score += 10

        return min(score, 100)


class ResearchSkill:
    def research(self, candidate: CandidateProfile, target: TargetProfile) -> str:
        return (
            f"{target.name} is a {target.role} at {target.company}. "
            f"This is relevant because the role sits in an AI or product-focused hiring context and the candidate has "
            f"experience in {', '.join(candidate.experience[:2])}."
        )


class PersonalizationSkill:
    def draft(self, candidate: CandidateProfile, target: TargetProfile, research_summary: str, score: int) -> str:
        first_name = target.name.split()[0]
        if not candidate.experience:
            experience_line = "AI systems and product engineering"
        else:
            experience_line = candidate.experience[0]

        return (
            f"Hi {first_name},\n\n"
            f"I noticed you're hiring for AI and product-focused work at {target.company}, and my background in "
            f"{experience_line} aligns closely with what your team is building. I’ve worked on LLM workflows, "
            f"agentic AI systems, and full-stack product engineering, and I’d love to connect and share my resume: "
            f"{candidate.resume_url}.\n\n"
            f"Thanks,\n{candidate.name}"
        )


class CriticSkill:
    def review(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        issues: List[Dict[str, str]] = []
        lower_message = message.lower()

        if "http" not in lower_message:
            issues.append({"code": "missing_resume_link", "message": "Resume link is missing."})

        personalization_tokens = [
            context.get("company", "").lower(),
            context.get("target_person", "").lower(),
            context.get("role", "").lower(),
        ]
        has_personalization = any(token and token in lower_message for token in personalization_tokens)
        if not has_personalization:
            issues.append({"code": "not_personalized", "message": "Message is not personalized."})

        if len(message) > 400:
            issues.append({"code": "too_long", "message": "Message is too long."})
        if any(word in lower_message for word in ["dear", "i hope this email finds you well"]):
            issues.append({"code": "spammy", "message": "Message sounds generic or spammy."})

        if issues:
            return {"status": "fail", "issues": issues}
        return {"status": "pass", "issues": []}


class ApprovalSkill:
    def __init__(self, store: ReachAIStore | None = None):
        self.store = store or ReachAIStore()
        self.tokens: Dict[str, Dict[str, Any]] = {}

    def create_token(self, outreach_id: str) -> str:
        token = secrets.token_urlsafe(16)
        self.tokens[token] = {
            "outreach_id": outreach_id,
            "status": "PENDING_APPROVAL",
            "used": False,
        }
        return token

    def validate_token(self, token: str) -> bool:
        record = self.tokens.get(token)
        if record is not None:
            return bool(record and not record["used"])
        return self.store.validate_approval_token(token)

    def approve(self, token: str) -> bool:
        if token in self.tokens:
            record = self.tokens[token]
            if record["used"]:
                return False
            record["used"] = True
            record["status"] = "APPROVED"
            return True
        return self.store.approve_token(token)

    def reject(self, token: str) -> bool:
        if token in self.tokens:
            record = self.tokens[token]
            if record["used"]:
                return False
            record["used"] = True
            record["status"] = "REJECTED"
            return True
        return self.store.reject_token(token)

    def prepare_for_review(self, draft_message: str, outreach_id: str = "draft-1") -> Dict[str, Any]:
        token = self.create_token(outreach_id)
        self.store.save_outreach({
            "outreach_id": outreach_id,
            "target_name": "",
            "company": "",
            "status": "PENDING_APPROVAL",
            "message": draft_message,
        })
        return {
            "needs_approval": True,
            "status": "PENDING_APPROVAL",
            "message": draft_message,
            "approval_token": token,
        }

    def build_review_email(self, target_name: str, company: str, score: int, message: str, approval_token: str) -> Dict[str, str]:
        approve_url = f"https://example.com/approval/{approval_token}/approve"
        reject_url = f"https://example.com/approval/{approval_token}/reject"
        subject = f"[ReachAI] Approval required — {target_name}"
        body = (
            f"ReachAI outreach review\n\n"
            f"Target: {target_name}\n"
            f"Company: {company}\n"
            f"Score: {score}/100\n\n"
            f"Draft:\n{message}\n\n"
            f"Choose an action:\n"
            f"Approve: {approve_url}\n"
            f"Reject: {reject_url}"
        )
        return {
            "subject": subject,
            "body": body,
            "approve_url": approve_url,
            "reject_url": reject_url,
        }


class SendSkill:
    def send(self, draft_message: str, status: str = "PENDING_APPROVAL") -> Dict[str, str]:
        if status != "APPROVED":
            raise PermissionError("Human approval required before sending an outreach message.")
        return {"status": "queued", "channel": "email", "message": draft_message}


class ResearchAgent:
    def research(self, request: OutreachRequest) -> str:
        return (
            f"{request.target_person} is a {request.target_role} at {request.company}. "
            f"Context: {request.company_description}. "
            f"They are relevant because the opening is for {request.job_title} and the team is "
            f"building around: {request.job_context}."
        )


class MatchingAgent:
    def match(self, request: OutreachRequest) -> str:
        experience = ", ".join(request.candidate.experience[:3])
        strengths = ", ".join(request.candidate.strengths[:3])
        return (
            f"Candidate profile matches the role through experience in {experience} and strengths in "
            f"{strengths}. This is a credible fit for an AI engineering opening."
        )


class WriterAgent:
    def draft(self, request: OutreachRequest, research_summary: str, match_summary: str) -> str:
        settings = get_settings()

        if not settings.openai_api_key:
            return self._template_draft(request)

        match_line = (
            f"I noticed you’re hiring for {request.job_title} roles at {request.company}, and my experience in "
            f"{', '.join(request.candidate.experience[:2])} aligns closely with the work."
        )
        message = (
            f"Hi {request.target_person},\n\n"
            f"{match_line}\n\n"
            f"I’ve been building agentic AI systems and LLM-based workflows, and this role feels closely aligned with my background. "
            f"I’d love to connect and share my resume: {request.candidate.resume_url}.\n\n"
            f"Thanks for your time,\n{request.candidate.name}"
        )
        return message

    def _template_draft(self, request: OutreachRequest) -> str:
        experience = ", ".join(request.candidate.experience[:2])
        return (
            f"Hi {request.target_person},\n\n"
            f"I noticed you're hiring for {request.job_title} roles at {request.company}, and my experience in "
            f"{experience} is a strong match for the work. I’d love to connect and share my resume: "
            f"{request.candidate.resume_url}.\n\n"
            f"Thanks,\n{request.candidate.name}"
        )


class CriticAgent:
    def review(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        issues: List[Dict[str, str]] = []
        lower_message = message.lower()

        if "http" not in lower_message:
            issues.append({"code": "missing_resume_link", "message": "Resume link is missing."})

        personalization_tokens = [
            context.get("company", "").lower(),
            context.get("target_person", "").lower(),
            context.get("role", "").lower(),
        ]
        has_personalization = any(token and token in lower_message for token in personalization_tokens)
        if not has_personalization:
            issues.append({"code": "not_personalized", "message": "Message is not personalized."})

        if len(message) > 400:
            issues.append({"code": "too_long", "message": "Message is too long."})
        if any(word in lower_message for word in ["dear", "i hope this email finds you well"]):
            issues.append({"code": "spammy", "message": "Message sounds generic or spammy."})

        if issues:
            return {"status": "fail", "issues": issues}
        return {"status": "pass", "issues": []}


class OutreachWorkflow:
    def __init__(self):
        self.research_agent = ResearchAgent()
        self.matching_agent = MatchingAgent()
        self.writer_agent = WriterAgent()
        self.critic_agent = CriticAgent()

    def prepare_outreach(self, request: OutreachRequest) -> OutreachDraft:
        research_summary = self.research_agent.research(request)
        match_summary = self.matching_agent.match(request)
        message = self.writer_agent.draft(request, research_summary, match_summary)
        criticism = self.critic_agent.review(message, {
            "company": request.company,
            "target_person": request.target_person,
            "role": request.job_title,
        })

        if criticism["status"] == "fail":
            message = (
                f"Hi {request.target_person},\n\n"
                f"I noticed you're hiring for {request.job_title} roles at {request.company}, and my experience in "
                f"{', '.join(request.candidate.experience[:2])} is a close match for the work. "
                f"I'd love to connect and share my resume: {request.candidate.resume_url}.\n\n"
                f"Thanks,\n{request.candidate.name}"
            )

        return OutreachDraft(
            target_person=request.target_person,
            company=request.company,
            message=message,
            needs_approval=True,
            research_summary=research_summary,
            match_summary=match_summary,
        )

    def send_outreach(self, draft: OutreachDraft, approved: bool) -> Dict[str, str]:
        if not approved:
            raise ValueError("Human approval required before sending an outreach message.")
        return {"status": "queued", "message": draft.message}


class ReachAIOrchestrator:
    def __init__(self):
        self.profile_skill = ProfileSkill()
        self.target_discovery_skill = TargetDiscoverySkill()
        self.eligibility_skill = EligibilitySkill()
        self.scoring_skill = ScoringSkill()
        self.research_skill = ResearchSkill()
        self.personalization_skill = PersonalizationSkill()
        self.critic_skill = CriticSkill()
        self.approval_skill = ApprovalSkill()
        self.send_skill = SendSkill()

    def process_target(self, candidate: CandidateProfile, target: TargetProfile) -> Dict[str, Any]:
        normalized_target = self.target_discovery_skill.normalize_target(target)
        profile = self.profile_skill.load_profile(candidate)
        eligible = self.eligibility_skill.is_eligible(profile, normalized_target)
        score = self.scoring_skill.score(profile, normalized_target)

        if not eligible or score < 75:
            return {
                "eligible": False,
                "score": score,
                "reason": "Target did not pass the qualification threshold.",
            }

        research_summary = self.research_skill.research(profile, normalized_target)
        draft_message = self.personalization_skill.draft(profile, normalized_target, research_summary, score)
        critique = self.critic_skill.review(draft_message, {
            "company": normalized_target.company,
            "target_person": normalized_target.name,
            "role": normalized_target.role,
        })

        approval = self.approval_skill.prepare_for_review(draft_message, outreach_id=f"draft-{normalized_target.target_id or normalized_target.name.lower().replace(' ', '-')}")

        return {
            "eligible": True,
            "score": score,
            "research_summary": research_summary,
            "match_summary": f"Strong technical and role fit with score {score}.",
            "draft": {
                "message": draft_message,
                "needs_approval": approval["needs_approval"],
                "status": approval["status"],
                "approval_token": approval["approval_token"],
            },
            "critique": critique,
        }
