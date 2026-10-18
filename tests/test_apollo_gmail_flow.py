import json

import httpx
import pytest

from reachai.config import Settings
from reachai.integrations.apollo import ApolloClient
from reachai.models.candidate import CandidateProfile
from reachai.service import ReachAIService
from reachai.storage.database import Database
from reachai.workers import ApprovalWorker

OWNER = "aman@example.com"


def apollo_transport(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert request.headers["x-api-key"] == "test-apollo-key"
        if request.url.path.endswith("/mixed_people/api_search"):
            return httpx.Response(200, json={"people": [
                {"id": "p1", "first_name": "Priya", "title": "Engineering Manager", "has_email": True,
                 "organization": {"name": "Acme AI"}},
                {"id": "p2", "first_name": "Raj", "title": "Technical Recruiter", "has_email": True,
                 "organization": {"name": "NoJobs Inc"}},
                {"id": "p3", "first_name": "Lee", "title": "Hiring Manager", "has_email": False,
                 "organization": {"name": "Acme AI"}},
            ]})
        if request.url.path.endswith("/people/match"):
            pid = request.url.params["id"]
            org = {"p1": ("org-acme", "Acme AI"), "p2": ("org-nojobs", "NoJobs Inc")}[pid]
            return httpx.Response(200, json={"person": {
                "id": pid, "name": {"p1": "Priya Shah", "p2": "Raj Rao"}[pid],
                "title": "Engineering Manager" if pid == "p1" else "Technical Recruiter",
                "email": f"{pid}@{org[0]}.com", "email_status": "verified",
                "linkedin_url": f"http://www.linkedin.com/in/{pid}",
                "organization_id": org[0], "organization": {"id": org[0], "name": org[1]},
            }})
        if request.url.path.endswith("/organizations/org-acme/job_postings"):
            return httpx.Response(200, json={"organization_job_postings": [
                {"id": "j1", "title": "Senior AI Engineer", "url": "https://www.linkedin.com/jobs/view/1",
                 "country": "India", "posted_at": "2026-10-10T00:00:00+00:00"},
                {"id": "j2", "title": "Office Manager", "url": "https://x", "posted_at": "2026-10-12T00:00:00+00:00"},
            ]})
        if request.url.path.endswith("/organizations/org-nojobs/job_postings"):
            return httpx.Response(200, json={"organization_job_postings": []})
        return httpx.Response(404)
    return httpx.MockTransport(handler)


class FakeGmail:
    def __init__(self):
        self.approval_emails, self.outreach, self.inbox, self.read = [], [], [], []
        self.fail_outreach = False

    def authorized(self):
        return True

    def oauth_configured(self):
        return True

    def send_approval_request(self, recipient, subject, body, approval_token, html=None):
        self.approval_emails.append({"to": recipient, "subject": subject, "body": body, "html": html, "token": approval_token})
        return {"status": "sent"}

    def send_outreach(self, recipient, subject, body):
        if self.fail_outreach:
            return {"status": "failed", "error": "boom"}
        self.outreach.append({"to": recipient, "subject": subject, "body": body})
        return {"status": "sent"}

    def get_new_messages(self, query=""):
        return list(self.inbox)

    def mark_as_read(self, message_id):
        self.read.append(message_id)
        return True


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no seed data from the repo's data/ folder
    settings = Settings(db_path=str(tmp_path / "r.db"), candidate_path=str(tmp_path / "c.json"),
                        send_mode="gmail", apollo_api_key="test-apollo-key", daily_limit=5)
    svc = ReachAIService(settings=settings, db=Database(settings.db_path))
    svc.save_profile(CandidateProfile(
        name="Aman Singh", email=OWNER, resume_url="https://drive.example/resume",
        skills=["Python", "LLMs", "RAG"], experience=["Google Web Solutions Engineer Intern"],
        target_roles=["AI Engineer"], target_locations=["India", "Remote"],
    ))
    svc.calls = []
    svc.apollo = ApolloClient("test-apollo-key", transport=apollo_transport(svc.calls))
    svc.gmail = FakeGmail()
    svc.llm.client = None
    return svc


def test_run_cycle_finds_grounded_people_and_emails_each_draft(service):
    summary = service.run_cycle()

    added = summary["found"]["added"]
    assert [item["person"] for item in added] == ["Priya Shah (Acme AI)"]
    reasons = {item["reason"] for item in summary["found"]["skipped"]}
    assert reasons == {"no_matching_job_posting"}  # Raj's company has no AI Engineer posting
    assert summary["found"]["enriched"] == 2  # Lee had no email, so no credit was spent

    target = service.db.get_target("apollo-p1")
    assert target["email"] == "p1@org-acme.com"
    assert target["linkedin_url"] == "http://www.linkedin.com/in/p1"

    assert len(service.gmail.approval_emails) == 1
    email = service.gmail.approval_emails[0]
    assert email["to"] == OWNER
    assert "ref " + email["token"] in email["subject"]
    assert "Senior AI Engineer opening at Acme AI" in email["body"]
    assert "linkedin.com/in/p1" in email["html"] and "Approve &amp; send" in email["html"]
    assert service.gmail.outreach == []  # nothing is sent before approval

    # A second run does not re-enrich or re-draft the same person.
    again = service.run_cycle()
    assert again["found"]["added"] == [] and again["drafted"] == []


def test_reply_approve_sends_only_that_message(service):
    service.run_cycle()
    token = service.gmail.approval_emails[0]["token"]
    subject = service.gmail.approval_emails[0]["subject"]

    service.gmail.inbox = [
        # The approval email itself (contains the words APPROVE/REJECT) must not act.
        {"id": "m0", "from": OWNER, "subject": subject, "body": service.gmail.approval_emails[0]["body"]},
        # Someone else cannot approve.
        {"id": "m1", "from": "attacker@evil.com", "subject": "Re: " + subject, "body": "APPROVE"},
        {"id": "m2", "from": f"Aman <{OWNER}>", "subject": "Re: " + subject,
         "body": "Approve\n\nOn Sat, Oct 18, 2026 Aman <aman@example.com> wrote:\n> Reject: http://x"},
    ]
    decisions = service.process_replies()

    assert [d["action"] for d in decisions] == ["APPROVED"]
    assert decisions[0]["delivery"]["status"] == "SENT"
    assert [m["to"] for m in service.gmail.outreach] == ["p1@org-acme.com"]
    assert service.db.get_target("apollo-p1")["already_contacted"] is True
    # Processed messages are never applied twice.
    assert service.process_replies() == []
    assert token


def test_reply_quoting_approve_does_not_approve(tmp_path):
    db = Database(str(tmp_path / "r.db"))
    db.save_outreach({"id": "o1", "target_id": "t1", "channel": "email", "message": "m", "status": "PENDING_APPROVAL"})
    token = db.create_approval_token("o1")
    worker = ApprovalWorker(store=db, owner_email=OWNER)
    result = worker.process_email({
        "from": OWNER, "subject": f"Re: [ReachAI] ref {token}",
        "body": f"not this one\n\n> Or reply with APPROVE {token}",
    })
    assert result["action"] == "NO_ACTION"
    assert db.get_outreach("o1")["status"] == "PENDING_APPROVAL"


def test_failed_gmail_send_keeps_outreach_approved_and_daily_limit_holds(service):
    service.run_cycle()
    token = service.gmail.approval_emails[0]["token"]
    service.gmail.fail_outreach = True
    decision = service.decide(token, "approve")
    assert decision["delivery"]["status"] == "FAILED"
    outreach_id = decision["outreach_id"]
    assert service.db.get_outreach(outreach_id)["status"] == "APPROVED"

    service.settings.daily_limit = 0
    service.gmail.fail_outreach = False
    assert service.send_approved() == []
    assert service.gmail.outreach == []

    service.settings.daily_limit = 5
    assert service.send_approved() == [{"outreach_id": outreach_id, "status": "SENT"}]
