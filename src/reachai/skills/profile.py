import json
from pathlib import Path

from reachai.models.candidate import CandidateProfile


class ProfileSkill:
    def __init__(self, path: str = "data/candidate.json"):
        self.path = Path(path)

    def load(self) -> CandidateProfile:
        if not self.path.exists():
            return CandidateProfile(
                name="Aman Singh",
                email="",
                resume_url="https://example.com/resume",
                skills=["Python", "LLMs", "RAG", "AI Agents"],
                experience=["Product engineering", "LLM workflows"],
                strengths=["AI systems", "full-stack engineering"],
                target_roles=["AI Engineer", "ML Engineer"],
                target_locations=["Remote", "India"],
            )
        with self.path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return CandidateProfile.model_validate(data)
