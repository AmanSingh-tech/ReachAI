from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from reachai.agents.orchestrator import ReachAIOrchestrator
from reachai.config import Settings, get_settings
from reachai.integrations.apollo import ApolloClient, ApolloError
from reachai.integrations.gmail import GmailClient
from reachai.integrations.llm import LLMClient
from reachai.models.candidate import CandidateProfile
from reachai.models.job import Job
from reachai.models.target import TargetProfile
from reachai.skills.approval import ApprovalSkill
from reachai.skills.profile import ProfileSkill
from reachai.skills.scoring import ScoringSkill
from reachai.storage.database import Database
from reachai.workers import ApprovalWorker, SendWorker


class WorkflowError(ValueError):
    def __init__(self, message: str, *, code: str = "workflow_error"):
        super().__init__(message)
        self.code = code


def _stable_id(prefix: str, *parts: str) -> str:
    source = "|".join(part.strip().lower() for part in parts if part).encode("utf-8")
    digest = hashlib.sha256(source).hexdigest()[:10]
    slug_source = next((part for part in parts if part), prefix)
    slug = re.sub(r"[^a-z0-9]+", "-", slug_source.lower()).strip("-")[:32] or prefix
    return f"{prefix}-{slug}-{digest}"


class ReachAIService:
    """Application service joining the workflow, persistence, and delivery boundary."""

    def __init__(self, settings: Settings | None = None, db: Database | None = None):
        self.settings = settings or get_settings()
        self.db = db or Database(self.settings.db_path)
        self.profile = ProfileSkill(self.settings.candidate_path)
        self.orchestrator = ReachAIOrchestrator()
        self.scorer = ScoringSkill()
        self.gmail = GmailClient()
        self.apollo = ApolloClient(self.settings.apollo_api_key)
        self.llm = LLMClient(
            api_key=self.settings.openrouter_api_key or self.settings.openai_api_key,
            model=self.settings.llm_model,
            base_url=self.settings.openrouter_base_url,
        )
        self.bootstrap_local_data()

    def bootstrap_local_data(self) -> None:
        """Load the checked-in/example JSON records only when local tables are empty."""
        if not self.db.list_targets():
            self._load_json_records(Path("data/targets.json"), self.create_target)
        if not self.db.list_jobs():
            self._load_json_records(Path("data/jobs.json"), self.create_job)

    @staticmethod
    def _load_json_records(path: Path, saver: Any) -> None:
        if not path.exists():
            return
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(records, list):
                for record in records:
                    saver(record)
        except (OSError, ValueError, TypeError):
            # Invalid optional seed data must not prevent the application starting.
            return

    def get_profile(self) -> CandidateProfile:
        return self.profile.load()

    def save_profile(self, profile: CandidateProfile | dict[str, Any]) -> CandidateProfile:
        validated = profile if isinstance(profile, CandidateProfile) else CandidateProfile.model_validate(profile)
        return self.profile.save(validated)

    def create_target(self, payload: TargetProfile | dict[str, Any]) -> dict[str, Any]:
        target = payload if isinstance(payload, TargetProfile) else TargetProfile.model_validate(payload)
        if not target.target_id:
            email = str(target.email or "").strip().lower()
            linkedin_url = str(target.linkedin_url or "").strip().lower()
            existing = next((item for item in self.db.list_targets() if (
                (email and str(item.get("email") or "").strip().lower() == email)
                or (linkedin_url and str(item.get("linkedin_url") or "").strip().lower() == linkedin_url)
                or (
                    str(item.get("name", "")).strip().lower() == target.name.strip().lower()
                    and str(item.get("company", "")).strip().lower() == target.company.strip().lower()
                )
            )), None)
            target.target_id = existing["id"] if existing else _stable_id("target", target.name, target.company, target.title)
        self.db.save_target(target.model_dump())
        return self.db.get_target(target.target_id)

    def create_job(self, payload: Job | dict[str, Any]) -> dict[str, Any]:
        data = payload.model_dump() if isinstance(payload, Job) else dict(payload)
        if not data.get("job_id") and not data.get("id"):
            url = str(data.get("url") or "").strip().lower()
            title = str(data.get("title", "")).strip().lower()
            company = str(data.get("company", "")).strip().lower()
            existing = next((item for item in self.db.list_jobs() if (
                (url and str(item.get("url") or "").strip().lower() == url)
                or (
                    str(item.get("title", "")).strip().lower() == title
                    and str(item.get("company", "")).strip().lower() == company
                )
            )), None)
            data["job_id"] = existing["id"] if existing else _stable_id(
                "job", str(data.get("title", "")), str(data.get("company", "")), str(data.get("url", ""))
            )
        job = Job.model_validate({**data, "job_id": data.get("job_id") or data.get("id")})
        candidate = self.get_profile()
        job_data = job.model_dump()
        if job_data.get("score") is None:
            job_data["score"] = self.scorer.score_job(job_data, candidate.model_dump())
        self.db.save_job(job_data)
        return self.db.get_job(job.job_id)

    def list_targets(self) -> list[dict[str, Any]]:
        return self.db.list_targets()

    def list_jobs(self) -> list[dict[str, Any]]:
        jobs = self.db.list_jobs()
        candidate = self.get_profile()
        changed = False
        for job in jobs:
            if job.get("score") is None:
                job["score"] = self.scorer.score_job(job, candidate.model_dump())
                self.db.save_job(job)
                changed = True
        return self.db.list_jobs() if changed else jobs

    def _select_job(self, target: dict[str, Any], job_id: str | None) -> dict[str, Any]:
        if job_id:
            job = self.db.get_job(job_id)
            if not job:
                raise WorkflowError("The selected job does not exist.", code="job_not_found")
            return job
        jobs = self.list_jobs()
        same_company = [
            job for job in jobs
            if str(job.get("company", "")).strip().lower() == str(target.get("company", "")).strip().lower()
        ]
        candidates = same_company or jobs
        if not candidates:
            raise WorkflowError("Add at least one job before preparing outreach.", code="job_required")
        return max(candidates, key=lambda job: float(job.get("score") or 0))

    def prepare_outreach(
        self,
        target_id: str,
        job_id: str | None = None,
        *,
        send_approval_email: bool = False,
        use_llm: bool = False,
    ) -> dict[str, Any]:
        target_record = self.db.get_target(target_id)
        if not target_record:
            raise WorkflowError("The selected target does not exist.", code="target_not_found")
        if self.db.has_active_outreach(target_id):
            raise WorkflowError(
                "This target already has pending, approved, or sent outreach.",
                code="duplicate_outreach",
            )
        if self.db.email_already_contacted(str(target_record.get("email") or ""), exclude_target_id=target_id):
            raise WorkflowError("This email address was already contacted.", code="duplicate_outreach")
        if self.db.count_sent_today() >= self.settings.daily_limit:
            raise WorkflowError("The daily outreach limit has been reached.", code="daily_limit_exceeded")

        candidate = self.get_profile()
        if not candidate.resume_url:
            raise WorkflowError("Add a resume URL to the candidate profile first.", code="profile_incomplete")
        if send_approval_email:
            if not self._owner_email(candidate):
                raise WorkflowError("Set your real email in the candidate profile first.", code="profile_incomplete")
            if not self.gmail.authorized():
                raise WorkflowError("Gmail is not authorized. Run `reachai auth-gmail` first.", code="gmail_not_configured")
        target = TargetProfile.model_validate({
            **target_record,
            "target_id": target_record["id"],
        })
        job = self._select_job(target_record, job_id)
        result = self.orchestrator.run(candidate, target, job)
        if not result.get("eligible"):
            raise WorkflowError(
                f"Target is not eligible: {result.get('reason', 'qualification failed')}",
                code="target_ineligible",
            )
        critic = result.get("critic", {})
        if not critic.get("passed"):
            raise WorkflowError(
                f"Draft failed quality review: {', '.join(critic.get('issues', []))}",
                code="critic_failed",
            )

        llm_used = False
        llm_note: str | None = None
        if use_llm and not self.llm.client:
            llm_note = f"LLM {self.llm.describe()}; using the grounded template draft."
        if use_llm and self.llm.client:
            prompt = (
                "Write a concise professional outreach email using only the supplied JSON facts. "
                "Do not invent company, person, role, or candidate details. Keep the message under 500 characters, "
                "mention the company and job title, and include the exact resume URL. Return JSON with subject and message.\n\n"
                + json.dumps({
                    "candidate": candidate.model_dump(),
                    "target": target.model_dump(),
                    "job": job,
                    "research": result.get("research", {}),
                }, ensure_ascii=False)
            )
            generated = self.llm.generate(prompt)
            if isinstance(generated, dict) and str(generated.get("message", "")).strip():
                candidate_draft = {
                    **result["draft"],
                    "subject": str(generated.get("subject") or result["draft"].get("subject", "")).strip(),
                    "message": str(generated["message"]).strip(),
                }
                generated_critic = self.orchestrator.critic_skill.review(candidate_draft, {"company": target.company})
                message_lower = candidate_draft["message"].lower()
                required_facts_present = all((
                    candidate.resume_url in candidate_draft["message"],
                    target.company.lower() in message_lower,
                    str(job.get("title", "")).lower() in message_lower,
                ))
                if generated_critic.get("passed") and required_facts_present:
                    result["draft"] = candidate_draft
                    result["critic"] = generated_critic
                    critic = generated_critic
                    llm_used = True
                else:
                    llm_note = "LLM draft failed grounding checks; using the grounded template draft."
            else:
                llm_note = f"LLM call failed ({self.llm.last_error}); using the grounded template draft."

        outreach_id = f"outreach-{uuid4().hex[:12]}"
        draft = result["draft"]
        created_at = datetime.now(timezone.utc).isoformat()
        self.db.save_outreach({
            "id": outreach_id,
            "target_id": target_id,
            "job_id": job.get("id") or job.get("job_id"),
            "channel": "email",
            "subject": draft.get("subject", f"Interest in {job.get('title', 'the role')}"),
            "message": draft["message"],
            "match_score": result.get("score", 0),
            "status": "PENDING_APPROVAL",
            "created_at": created_at,
        })
        approval_token = self.db.create_approval_token(outreach_id, result.get("approval_token"))
        approval_email = ApprovalSkill().build_review_email(
            target_name=target.name,
            company=target.company,
            score=int(result.get("score", 0)),
            message=draft["message"],
            approval_token=approval_token,
            base_url=self.base_url,
            target_title=target.title,
            target_email=target.email or "",
            linkedin_url=target.linkedin_url or "",
            job_title=str(job.get("title") or ""),
            job_url=str(job.get("url") or ""),
            outreach_subject=str(draft.get("subject") or ""),
        )
        self.db.add_audit_event("outreach", outreach_id, "DRAFT_CREATED")
        approval_delivery: dict[str, Any] = {"status": "not_requested"}
        if send_approval_email:
            approval_delivery = self.gmail.send_approval_request(
                recipient=self._owner_email(candidate),
                subject=approval_email["subject"],
                body=approval_email["body"],
                html=approval_email["html"],
                approval_token=approval_token,
            )
            self.db.add_audit_event(
                "outreach", outreach_id, "APPROVAL_EMAIL_" + str(approval_delivery.get("status", "")).upper(),
                str(approval_delivery.get("error") or ""),
            )
        return {
            "status": "outreach_ready",
            "outreach_id": outreach_id,
            "approval_token": approval_token,
            "approval_email": approval_email,
            "approval_delivery": approval_delivery,
            "draft": draft,
            "research": result.get("research"),
            "score": result.get("score", 0),
            "critic": critic,
            "llm_used": llm_used,
            "llm_note": llm_note,
        }

    def decide(self, token: str, action: str) -> dict[str, Any]:
        action = action.lower()
        if action == "approve":
            accepted = self.db.approve_token(token)
            status = "APPROVED"
        elif action == "reject":
            accepted = self.db.reject_token(token)
            status = "REJECTED"
        else:
            raise WorkflowError("Action must be approve or reject.", code="invalid_action")
        if not accepted:
            raise WorkflowError("Approval token is invalid, expired, or already used.", code="invalid_token")
        result: dict[str, Any] = {"status": status, "token": token}
        if status == "APPROVED":
            # Approval is the instruction to send; this one message goes out now
            # unless the daily limit defers it to the background sender.
            outreach_id = self.db.outreach_id_for_token(token)
            if outreach_id:
                result["outreach_id"] = outreach_id
                result["delivery"] = self._send_worker().process_one(outreach_id)
        return result

    @property
    def base_url(self) -> str:
        return (self.settings.public_url or f"http://{self.settings.host}:{self.settings.port}").rstrip("/")

    @staticmethod
    def _owner_email(candidate: CandidateProfile) -> str:
        email = (candidate.email or "").strip()
        return "" if not email or "@" not in email or email.upper() == "YOUR_EMAIL" else email

    def _send_worker(self) -> SendWorker:
        return SendWorker(
            store=self.db,
            gmail_client=self.gmail,
            send_mode=self.settings.send_mode,
            daily_limit=self.settings.daily_limit,
        )

    def send_approved(self) -> list[dict[str, str]]:
        """Send approved messages that are still waiting (e.g. deferred by the daily limit)."""
        return self._send_worker().process_pending()

    def process_replies(self) -> list[dict[str, Any]]:
        """Apply APPROVE/REJECT replies to approval emails, then send what was approved."""
        owner = self._owner_email(self.get_profile())
        if not owner or not self.gmail.authorized():
            return []
        worker = ApprovalWorker(store=self.db, owner_email=owner)
        decisions = []
        for message in self.gmail.get_new_messages(query="subject:ReachAI subject:ref newer_than:14d"):
            if not self.db.claim_message(str(message.get("id"))):
                continue
            decision = worker.process_email(message)
            if decision["action"] == "APPROVED":
                outreach_id = self.db.outreach_id_for_token(decision["token"])
                if outreach_id:
                    decision["delivery"] = self._send_worker().process_one(outreach_id)
            if decision["action"] != "NO_ACTION":
                self.gmail.mark_as_read(str(message.get("id")))
                decisions.append(decision)
        return decisions

    def find_people(self, max_enrich: int | None = None) -> dict[str, Any]:
        """Find contacts at companies with open roles matching the profile, via Apollo.

        Only people with an Apollo-verified work email and a real, matching job
        posting at their company are stored, so every draft is grounded.
        """
        if not self.apollo.configured():
            raise WorkflowError("Set APOLLO_API_KEY in .env first.", code="apollo_not_configured")
        candidate = self.get_profile()
        if not candidate.target_roles:
            raise WorkflowError("Add target roles to the candidate profile first.", code="profile_incomplete")
        budget = self.settings.enrich_per_run if max_enrich is None else max_enrich
        excluded = {company.strip().lower() for company in candidate.exclude_companies}
        known = {item["id"] for item in self.db.list_targets()}
        locations = [loc for loc in candidate.target_locations if loc.strip().lower() != "remote"]
        summary: dict[str, Any] = {"searched": 0, "enriched": 0, "added": [], "skipped": []}
        postings_cache: dict[str, list[dict[str, Any]]] = {}
        seen: set[str] = set()

        try:
            for role in candidate.target_roles:
                people = self.apollo.search_people(candidate.outreach_titles, hiring_for=role, job_locations=locations)
                summary["searched"] += len(people)
                for person in people:
                    if summary["enriched"] >= budget:
                        return summary
                    apollo_id = str(person["apollo_id"])
                    target_id = f"apollo-{apollo_id}"
                    company = str(person.get("company") or "")
                    if apollo_id in seen or target_id in known or not person.get("has_email"):
                        continue
                    seen.add(apollo_id)
                    if company.strip().lower() in excluded:
                        summary["skipped"].append({"company": company, "reason": "excluded_company"})
                        continue

                    enriched = self.apollo.enrich_person(apollo_id)
                    summary["enriched"] += 1
                    label = f"{enriched.get('name') or person.get('first_name')} ({company})"
                    if not enriched.get("email") or enriched.get("email_status") != "verified":
                        summary["skipped"].append({"person": label, "reason": "no_verified_email"})
                        continue
                    if self.db.email_already_contacted(enriched["email"]):
                        summary["skipped"].append({"person": label, "reason": "already_contacted"})
                        continue
                    org_id = enriched.get("organization_id")
                    if not org_id:
                        summary["skipped"].append({"person": label, "reason": "no_company_record"})
                        continue
                    if org_id not in postings_cache:
                        postings_cache[org_id] = self.apollo.job_postings(org_id)
                    posting = self._matching_posting(postings_cache[org_id], candidate.target_roles)
                    if not posting:
                        summary["skipped"].append({"person": label, "reason": "no_matching_job_posting"})
                        continue

                    company = enriched.get("company") or company
                    job = self.create_job({
                        "job_id": f"apollo-job-{posting['id']}",
                        "title": posting["title"],
                        "company": company,
                        "url": posting.get("url"),
                        "location": ", ".join(filter(None, (posting.get("city"), posting.get("country")))) or None,
                        "description": f"Job posting listed by Apollo, posted {str(posting.get('posted_at') or '')[:10]}.",
                        "source": "apollo",
                        "discovered_at": posting.get("posted_at"),
                    })
                    target = self.create_target({
                        "target_id": target_id,
                        "name": enriched["name"],
                        "title": enriched.get("title") or person.get("title") or "",
                        "company": company,
                        "email": enriched["email"],
                        "linkedin_url": enriched.get("linkedin_url"),
                        "location": enriched.get("location"),
                        "headline": enriched.get("headline"),
                        "source": "apollo",
                    })
                    known.add(target_id)
                    summary["added"].append({"target_id": target["id"], "job_id": job["id"], "person": label, "job": job["title"]})
        except ApolloError as exc:
            summary["error"] = str(exc)
        return summary

    @staticmethod
    def _matching_posting(postings: list[dict[str, Any]], roles: list[str]) -> dict[str, Any] | None:
        wanted = [role.strip().lower() for role in roles if role.strip()]
        matches = [p for p in postings if p.get("id") and p.get("title") and any(r in str(p["title"]).lower() for r in wanted)]
        return max(matches, key=lambda p: str(p.get("posted_at") or ""), default=None)

    def run_cycle(self, find: bool = True) -> dict[str, Any]:
        """One full pass: find people, draft for each, and email each draft for approval."""
        summary: dict[str, Any] = {"found": None, "drafted": [], "not_drafted": []}
        pairs: list[tuple[str, str | None]] = []
        if find:
            summary["found"] = self.find_people()
            pairs = [(item["target_id"], item["job_id"]) for item in summary["found"]["added"]]
        pending = {item["target_id"] for item in self.db.list_outreach()}
        for target in self.db.list_targets():
            if target["source"] == "apollo" and target["id"] not in pending and not target["already_contacted"]:
                if all(target["id"] != existing for existing, _ in pairs):
                    pairs.append((target["id"], None))
        for target_id, job_id in pairs:
            try:
                prepared = self.prepare_outreach(target_id, job_id, send_approval_email=True, use_llm=True)
                summary["drafted"].append({
                    "target_id": target_id,
                    "outreach_id": prepared["outreach_id"],
                    "approval_email": prepared["approval_delivery"].get("status"),
                })
            except WorkflowError as exc:
                summary["not_drafted"].append({"target_id": target_id, "reason": str(exc)})
        return summary

    def send(self, outreach_id: str) -> dict[str, str]:
        result = self._send_worker().process_one(outreach_id)
        if result.get("status") != "SENT":
            raise WorkflowError(result.get("error", "Outreach is not approved."), code=result.get("status", "send_failed").lower())
        return result

    def list_outreach(self) -> list[dict[str, Any]]:
        targets = {item["id"]: item for item in self.db.list_targets()}
        jobs = {item["id"]: item for item in self.db.list_jobs()}
        records = self.db.list_outreach()
        for record in records:
            record["target"] = targets.get(record.get("target_id"))
            record["job"] = jobs.get(record.get("job_id"))
            record["approval_token"] = self.db.get_active_approval_token(record["id"])
        return records

    def status(self) -> dict[str, Any]:
        counts = self.db.status_counts()
        candidate = self.get_profile()
        warnings = []
        if not candidate.email or candidate.email.upper() == "YOUR_EMAIL":
            warnings.append("Candidate email is not configured.")
        if not candidate.resume_url or "example.com" in candidate.resume_url:
            warnings.append("Candidate resume URL still uses a placeholder.")
        if not self.llm.client:
            warnings.append(f"LLM {self.llm.describe()}; drafts use the grounded template.")
        if not self.apollo.configured():
            warnings.append("APOLLO_API_KEY is not set; people search is disabled.")
        if self.settings.send_mode == "gmail" and not self.gmail.authorized():
            warnings.append("Gmail send mode is enabled but Gmail is not authorized; run `reachai auth-gmail`.")
        sent_today = self.db.count_sent_today()
        return {
            "status": "ok",
            "targets": len(self.db.list_targets()),
            "jobs": len(self.db.list_jobs()),
            "pending_approval": counts.get("PENDING_APPROVAL", 0),
            "approved": counts.get("APPROVED", 0),
            "sent": counts.get("SENT", 0),
            "rejected": counts.get("REJECTED", 0),
            "sent_today": sent_today,
            "daily_limit": self.settings.daily_limit,
            "send_mode": self.settings.send_mode,
            "gmail_configured": self.gmail.oauth_configured(),
            "gmail_authorized": self.gmail.authorized(),
            "apollo_configured": self.apollo.configured(),
            "approval_base_url": self.base_url,
            "llm_configured": bool(self.llm.client),
            "llm_model": self.llm.describe(),
            "warnings": warnings,
        }
