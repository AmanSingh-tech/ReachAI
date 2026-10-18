from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class CandidateProfile(BaseModel):
    name: str
    email: str = ""
    resume_url: str = ""
    skills: List[str] = Field(default_factory=list)
    experience: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    target_roles: List[str] = Field(default_factory=list)
    target_locations: List[str] = Field(default_factory=list)
    # Who to contact at hiring companies (used for Apollo people search).
    outreach_titles: List[str] = Field(default_factory=lambda: [
        "Technical Recruiter",
        "Talent Acquisition",
        "Engineering Manager",
        "Hiring Manager",
        "Head of Engineering",
        "Founder",
    ])
    exclude_companies: List[str] = Field(default_factory=list)
