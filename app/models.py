from typing import List, Optional

from pydantic import BaseModel, Field


class CandidateProfile(BaseModel):
    name: str
    email: str = ""
    resume_url: str
    skills: List[str] = Field(default_factory=list)
    experience: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    bio: str = ""
    target_roles: List[str] = Field(default_factory=list)


class TargetProfile(BaseModel):
    target_id: str = ""
    name: str
    role: str
    company: str
    profile_url: str = ""
    source: str = "csv_import"
    status: str = "discovered"
    notes: str = ""


class OutreachRequest(BaseModel):
    target_person: str
    target_role: str
    company: str
    company_description: str
    job_title: str
    job_context: str
    candidate: CandidateProfile


class OutreachDraft(BaseModel):
    target_person: str
    company: str
    message: str
    needs_approval: bool = True
    status: str = "PENDING_APPROVAL"
    approval_token: str = ""
    research_summary: str
    match_summary: str
