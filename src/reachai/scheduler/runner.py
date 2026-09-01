from __future__ import annotations

from reachai.agents.orchestrator import ReachAIOrchestrator
from reachai.models.candidate import CandidateProfile
from reachai.models.target import TargetProfile


def main() -> None:
    candidate = CandidateProfile(
        name="Aman Kumar Singh",
        email="aman@example.com",
        resume_url="https://example.com/resume",
        skills=["Python", "LLMs", "RAG", "AI Agents"],
        experience=["Product engineering", "LLM workflows"],
        strengths=["AI systems", "full-stack engineering"],
        target_roles=["AI Engineer", "ML Engineer"],
    )
    target = TargetProfile(
        name="Sarah Chen",
        title="Hiring Manager",
        company="Northstar Labs",
        linkedin_url="https://linkedin.com/in/example",
        source="local_runner",
    )
    result = ReachAIOrchestrator().run(candidate, target)
    print(result)


if __name__ == "__main__":
    main()
