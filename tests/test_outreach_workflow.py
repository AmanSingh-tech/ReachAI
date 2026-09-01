import pytest

from app.config import get_settings
from app.models import CandidateProfile, OutreachDraft, OutreachRequest, TargetProfile
from app.service import ApprovalSkill, OutreachWorkflow, ReachAIOrchestrator, SendSkill
from app.storage import ReachAIStore
from app.workers import ApprovalWorker, SendWorker


def test_settings_reads_llm_configuration_from_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")

    settings = get_settings()

    assert settings.openai_api_key == "test-key"
    assert settings.llm_model == "gpt-4o-mini"


def test_workflow_builds_personalized_draft_and_requires_approval():
    candidate = CandidateProfile(
        name="Aisha Patel",
        resume_url="https://example.com/resume",
        experience=["LLM application development", "agentic workflows", "RAG systems"],
        strengths=["AI Engineer", "productized ML systems"],
        bio="Built agentic AI systems and shipped LLM workflows for enterprise clients.",
    )

    request = OutreachRequest(
        target_person="Sarah Chen",
        target_role="Hiring Manager",
        company="Northstar Labs",
        company_description="YC-backed startup building AI tools for developers.",
        job_title="AI Engineer",
        job_context="Hiring for AI engineering roles across product and platform teams.",
        candidate=candidate,
    )

    workflow = OutreachWorkflow()
    draft = workflow.prepare_outreach(request)

    assert draft.needs_approval is True
    assert "Sarah" in draft.message
    assert "Northstar" in draft.message
    assert "https://example.com/resume" in draft.message
    assert len(draft.message) < 400


def test_critic_flags_generic_message_without_personalization_or_resume_link():
    workflow = OutreachWorkflow()
    weak_message = "Hi there, I would love to connect. I am very interested in your role."

    findings = workflow.critic_agent.review(weak_message, context={"company": "ExampleAI"})

    assert findings["status"] == "fail"
    assert any(item["code"] == "missing_resume_link" for item in findings["issues"])
    assert any(item["code"] == "not_personalized" for item in findings["issues"])


def test_human_approval_is_required_before_sending():
    workflow = OutreachWorkflow()
    request = OutreachRequest(
        target_person="Priya Singh",
        target_role="Recruiter",
        company="SignalForge",
        company_description="AI recruiting automation platform.",
        job_title="ML Engineer",
        job_context="Looking for ML engineers with LLM system experience.",
        candidate=CandidateProfile(
            name="Aisha Patel",
            resume_url="https://example.com/resume",
            experience=["LLM systems", "MLOps"],
            strengths=["ML engineering"],
            bio="Experienced in generative AI systems and production ML.",
        ),
    )

    draft = workflow.prepare_outreach(request)

    try:
        workflow.send_outreach(draft, approved=False)
        assert False, "Expected approval gate failure"
    except ValueError:
        pass

    result = workflow.send_outreach(draft, approved=True)
    assert result["status"] == "queued"


def test_writer_falls_back_to_template_when_llm_key_is_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    workflow = OutreachWorkflow()

    request = OutreachRequest(
        target_person="Priya Singh",
        target_role="Recruiter",
        company="SignalForge",
        company_description="AI recruiting automation platform.",
        job_title="ML Engineer",
        job_context="Looking for ML engineers with LLM system experience.",
        candidate=CandidateProfile(
            name="Aisha Patel",
            resume_url="https://example.com/resume",
            experience=["LLM systems", "MLOps"],
            strengths=["ML engineering"],
            bio="Experienced in generative AI systems and production ML.",
        ),
    )

    draft = workflow.prepare_outreach(request)

    assert "Hi Priya Singh" in draft.message
    assert "https://example.com/resume" in draft.message


def test_orchestrator_qualifies_real_target_and_generates_approved_draft():
    candidate = CandidateProfile(
        name="Aman Kumar Singh",
        email="pendulum4441@gmail.com",
        resume_url="https://example.com/aman-resume",
        skills=["Python", "LLMs", "RAG", "Agents", "Next.js", "Node.js"],
        experience=[
            "Google Web Solutions Engineer Intern",
            "AlgoUniversity Software Engineering Co-op Intern",
            "Built agentic AI systems and LLM workflows",
        ],
        strengths=["AI systems", "full-stack product engineering", "LLM workflows"],
        bio="Built agentic AI systems and shipped LLM workflows for enterprise clients.",
        target_roles=["AI Engineer", "ML Engineer", "Applied AI Engineer"],
    )
    target = TargetProfile(
        name="Sarah Chen",
        role="Hiring Manager",
        company="Northstar Labs",
        profile_url="https://linkedin.com/in/sarah-chen",
        source="csv_import",
        status="discovered",
    )

    orchestrator = ReachAIOrchestrator()
    result = orchestrator.process_target(candidate, target)

    assert result["eligible"] is True
    assert result["score"] >= 75
    assert result["draft"]["needs_approval"] is True
    assert "Hi Sarah" in result["draft"]["message"]
    assert "https://example.com/aman-resume" in result["draft"]["message"]


def test_send_skill_requires_approved_status():
    with pytest.raises(PermissionError):
        SendSkill().send("message", status="PENDING_APPROVAL")

    result = SendSkill().send("message", status="APPROVED")
    assert result["status"] == "queued"


def test_approval_skill_creates_single_use_token_and_enforces_state():
    approval = ApprovalSkill()
    token = approval.create_token("draft-1")

    assert token
    assert approval.validate_token(token) is True
    assert approval.approve(token) is True
    assert approval.validate_token(token) is False
    assert approval.reject(token) is False


def test_store_persists_outreach_and_approval_state(tmp_path):
    db_path = tmp_path / "reachai.db"
    store = ReachAIStore(str(db_path))

    store.save_outreach({
        "outreach_id": "draft-1",
        "target_name": "Sarah Chen",
        "company": "Northstar Labs",
        "status": "PENDING_APPROVAL",
        "message": "Hi Sarah",
    })

    token = store.create_approval_token("draft-1")
    assert store.validate_approval_token(token) is True
    assert store.get_outreach("draft-1")["status"] == "PENDING_APPROVAL"

    assert store.approve_token(token) is True
    assert store.get_outreach("draft-1")["status"] == "APPROVED"
    assert store.validate_approval_token(token) is False


def test_approval_email_payload_includes_action_links():
    approval = ApprovalSkill()
    email = approval.build_review_email(
        target_name="Sarah Chen",
        company="Northstar Labs",
        score=92,
        message="Hi Sarah, I would love to connect.",
        approval_token="abc123",
    )

    assert email["subject"] == "[ReachAI] Approval required — Sarah Chen"
    assert "approve" in email["body"].lower()
    assert "reject" in email["body"].lower()
    assert "abc123" in email["approve_url"]


def test_approval_worker_approves_email_reply_and_send_worker_only_sends_approved_outreach(tmp_path):
    store = ReachAIStore(str(tmp_path / "reachai.db"))
    store.save_outreach({
        "outreach_id": "draft-1",
        "target_name": "Sarah Chen",
        "company": "Northstar Labs",
        "status": "PENDING_APPROVAL",
        "message": "Hi Sarah",
    })
    token = store.create_approval_token("draft-1")

    worker = ApprovalWorker(store=store)
    decision = worker.process_email({
        "from": "aman@example.com",
        "body": f"APPROVE {token}",
    })

    assert decision["action"] == "APPROVED"
    assert store.get_outreach("draft-1")["status"] == "APPROVED"

    send_worker = SendWorker(store=store)
    assert send_worker.process_pending() == [{"outreach_id": "draft-1", "status": "SENT"}]

    assert send_worker.process_pending() == []
