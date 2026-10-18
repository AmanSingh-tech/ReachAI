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

    def save(self, profile: CandidateProfile) -> CandidateProfile:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary_path.write_text(
            json.dumps(profile.model_dump(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(self.path)
        return profile
