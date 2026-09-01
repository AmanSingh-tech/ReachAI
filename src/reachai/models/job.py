from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class Job(BaseModel):
    job_id: str
    title: str
    company: str
    location: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    source: str = "manual"
    score: Optional[float] = None
    discovered_at: Optional[str] = None
