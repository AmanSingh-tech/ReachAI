from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class ResearchFact(BaseModel):
    fact: str
    source: str
    confidence: float = 0.0


class ResearchResult(BaseModel):
    company_summary: str = ""
    role_summary: str = ""
    hiring_signal: str = ""
    relevant_fact: str = ""
    evidence: List[ResearchFact] = []
    confidence: float = 0.0
