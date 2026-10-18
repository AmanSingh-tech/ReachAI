from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any, Dict, List

import httpx


class ApolloError(RuntimeError):
    pass


class ApolloClient:
    """Minimal Apollo.io REST client.

    Credit use (per Apollo docs): people search is free, people enrichment costs
    ~1 credit per person with an email, job postings cost 1 credit per page.
    """

    BASE_URL = "https://api.apollo.io/api/v1"

    def __init__(self, api_key: str | None = None, transport: httpx.BaseTransport | None = None):
        self.api_key = (api_key if api_key is not None else os.getenv("APOLLO_API_KEY", "")).strip()
        self._http = httpx.Client(
            base_url=self.BASE_URL,
            timeout=30.0,
            transport=transport,
            headers={"x-api-key": self.api_key, "Content-Type": "application/json", "Cache-Control": "no-cache"},
        )

    def configured(self) -> bool:
        return bool(self.api_key) and not self.api_key.lower().startswith("your")

    def _request(self, method: str, path: str, params: Any = None) -> Dict[str, Any]:
        if not self.configured():
            raise ApolloError("APOLLO_API_KEY is not configured.")
        response = self._http.request(method, path, params=params)
        if response.status_code == 401:
            raise ApolloError("Apollo rejected the API key (401).")
        if response.status_code == 403:
            raise ApolloError(f"Apollo API key lacks access to {path} (403). Use a master key or enable this endpoint.")
        if response.status_code == 429:
            raise ApolloError("Apollo rate limit reached (429); try again later.")
        if response.status_code >= 400:
            raise ApolloError(f"Apollo {path} failed ({response.status_code}): {response.text[:200]}")
        return response.json()

    def search_people(
        self,
        titles: List[str],
        hiring_for: str | None = None,
        job_locations: List[str] | None = None,
        posted_within_days: int = 30,
        per_page: int = 25,
        page: int = 1,
    ) -> List[Dict[str, Any]]:
        """Free search: people with ``titles`` at companies with recent ``hiring_for`` postings."""
        params: List[tuple[str, Any]] = [("page", page), ("per_page", per_page), ("include_similar_titles", "true")]
        params += [("person_titles[]", title) for title in titles]
        if hiring_for:
            params.append(("q_organization_job_titles[]", hiring_for))
            since = date.today() - timedelta(days=posted_within_days)
            params.append(("organization_job_posted_at_range[min]", since.isoformat()))
        params += [("organization_job_locations[]", loc) for loc in job_locations or []]
        data = self._request("POST", "/mixed_people/api_search", params=params)
        return [
            {
                "apollo_id": person.get("id"),
                "first_name": person.get("first_name"),
                "title": person.get("title"),
                "company": (person.get("organization") or {}).get("name"),
                "has_email": bool(person.get("has_email")),
            }
            for person in data.get("people", [])
            if person.get("id")
        ]

    def enrich_person(self, apollo_id: str) -> Dict[str, Any]:
        """Paid lookup: full name, work email, LinkedIn URL and organization for one person."""
        data = self._request("POST", "/people/match", params={"id": apollo_id, "reveal_personal_emails": "false"})
        person = data.get("person") or {}
        organization = person.get("organization") or {}
        location = ", ".join(part for part in (person.get("city"), person.get("country")) if part)
        return {
            "apollo_id": person.get("id") or apollo_id,
            "name": person.get("name") or " ".join(filter(None, (person.get("first_name"), person.get("last_name")))),
            "title": person.get("title"),
            "headline": person.get("headline"),
            "email": person.get("email"),
            "email_status": person.get("email_status"),
            "linkedin_url": person.get("linkedin_url"),
            "location": location or None,
            "company": organization.get("name"),
            "organization_id": person.get("organization_id") or organization.get("id"),
            "company_domain": organization.get("primary_domain"),
        }

    def job_postings(self, organization_id: str, per_page: int = 100) -> List[Dict[str, Any]]:
        data = self._request("GET", f"/organizations/{organization_id}/job_postings", params={"page": 1, "per_page": per_page})
        return data.get("organization_job_postings", [])
