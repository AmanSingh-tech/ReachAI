from __future__ import annotations

from typing import Any, Dict, List


class ApolloClient:
    def search_people(self, titles: List[str], companies: List[str] | None = None) -> List[Dict[str, Any]]:
        return [{
            "name": "Sarah Chen",
            "title": "Hiring Manager",
            "company": "Northstar Labs",
            "email": "sarah@northstarlabs.ai",
            "linkedin_url": "https://linkedin.com/in/example",
        }]

    def enrich_person(self, person_id: str) -> Dict[str, Any]:
        return {"person_id": person_id, "email": "person@example.com"}
