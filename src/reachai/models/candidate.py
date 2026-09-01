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
