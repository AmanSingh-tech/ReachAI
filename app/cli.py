from __future__ import annotations

import argparse
import json

from app.models import CandidateProfile, TargetProfile
from app.orchestrator import LocalReachAI


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ReachAI local outreach workflow")
    parser.add_argument("--name", default="Aman Kumar Singh")
    parser.add_argument("--email", default="aman@example.com")
    parser.add_argument("--resume-url", default="https://example.com/resume")
    parser.add_argument("--target-name", default="Sarah Chen")
    parser.add_argument("--target-role", default="Hiring Manager")
    parser.add_argument("--company", default="Northstar Labs")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    candidate = CandidateProfile(
        name=args.name,
        email=args.email,
        resume_url=args.resume_url,
        skills=["Python", "LLMs", "RAG", "Agents", "Next.js", "Node.js"],
        experience=["LLM workflow engineering", "AI product prototyping", "full-stack product building"],
        strengths=["AI systems", "agentic workflows", "MLOps", "product engineering"],
        target_roles=["AI Engineer", "Applied AI Engineer", "ML Engineer"],
    )
    target = TargetProfile(
        name=args.target_name,
        role=args.target_role,
        company=args.company,
        profile_url="https://example.com/profile",
        source="local_cli",
    )

    result = LocalReachAI().run(candidate, target)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
