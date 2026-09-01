from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class TargetProfile(BaseModel):
    target_id: str = ""
    name: str
    title: str = ""
    company: str
    linkedin_url: Optional[str] = None
    email: Optional[str] = None
    source: str = "manual_import"
    location: Optional[str] = None
    headline: Optional[str] = None
    status: str = "DISCOVERED"
    already_contacted: bool = False
    blocked: bool = False
