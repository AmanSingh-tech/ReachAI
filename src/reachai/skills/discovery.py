from __future__ import annotations

from typing import Any, Dict, List

from reachai.storage.database import Database


class DiscoverySource:
    def search(self, query: dict) -> list[dict]:
        raise NotImplementedError


class LocalJobsSource(DiscoverySource):
    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    def search(self, query: dict) -> list[dict]:
        jobs = self.db.list_jobs()
        keywords = query.get("keywords") or []
        if not isinstance(keywords, list):
            keywords = [keywords]
        keywords = [str(item).lower() for item in keywords if item]

        def matches(job: dict) -> bool:
            if not keywords:
                return True
            haystack = " ".join([
                job.get("title", ""),
                job.get("company", ""),
                job.get("source", ""),
                job.get("url", ""),
            ]).lower()
            return any(keyword in haystack for keyword in keywords)

        return [
            {
                "job_id": job.get("id") or job.get("job_id"),
                "title": job.get("title"),
                "company": job.get("company"),
                "location": job.get("location"),
                "url": job.get("url"),
                "description": job.get("description"),
                "source": job.get("source", "local_db"),
            }
            for job in jobs
            if matches(job)
        ]


class LinkedInJobsSource(DiscoverySource):
    def search(self, query: dict) -> list[dict]:
        return [{
            "job_id": "linkedin-demo-1",
            "title": "AI Engineer",
            "company": "Northstar Labs",
            "location": "Remote",
            "url": "https://example.com/jobs/1",
            "description": "Build LLM workflows, AI products, Python services, RAG systems.",
            "source": "linkedin",
        }]


class FreehireSource(DiscoverySource):
    def search(self, query: dict) -> list[dict]:
        return [{
            "job_id": "freehire-demo-1",
            "title": "ML Engineer",
            "company": "SignalForge",
            "location": "Remote",
            "url": "https://example.com/jobs/2",
            "description": "Python, ML, agents, LLM tooling.",
            "source": "freehire",
        }]


class DiscoverySkill:
    def __init__(self, db: Database | None = None):
        self.db = db or Database()
        self.sources = [LocalJobsSource(self.db), LinkedInJobsSource(), FreehireSource()]

    def discover(self, query: dict | None = None) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen = set()
        for source in self.sources:
            for item in source.search(query or {}):
                identity = item.get("job_id") or (item.get("title", ""), item.get("company", ""))
                if identity in seen:
                    continue
                seen.add(identity)
                items.append(item)
        return items
