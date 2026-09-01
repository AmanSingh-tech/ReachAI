from reachai.agents.orchestrator import ReachAIOrchestrator
from reachai.models.candidate import CandidateProfile
from reachai.models.target import TargetProfile


def test_orchestrator_generates_approval_ready_draft():
    candidate = CandidateProfile(
        name="Aman Kumar Singh",
        email="aman@example.com",
        resume_url="https://example.com/resume",
        skills=["Python", "LLMs", "RAG", "AI Agents"],
        experience=["LLM workflow engineering", "product engineering"],
        strengths=["AI systems", "full-stack engineering"],
        target_roles=["AI Engineer", "ML Engineer"],
    )
    target = TargetProfile(
        name="Sarah Chen",
        title="Hiring Manager",
        company="Northstar Labs",
        source="local_test",
    )

    result = ReachAIOrchestrator().run(candidate, target)

    assert result["eligible"] is True
    assert result["score"] >= 75
    assert "approval_token" in result
    assert "approval_email" in result
