from reachai.config import Settings
from reachai.models.candidate import CandidateProfile
from reachai.service import ReachAIService
from reachai.storage.database import Database


def test_service_runs_persistent_end_to_end_workflow(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / "reachai.db"),
        candidate_path=str(tmp_path / "candidate.json"),
        send_mode="dry-run",
    )
    service = ReachAIService(settings=settings, db=Database(settings.db_path))
    service.save_profile(CandidateProfile(
        name="Aman Singh",
        email="aman@example.com",
        resume_url="https://example.com/resume",
        skills=["Python", "LLMs", "RAG", "AI Agents"],
        experience=["LLM workflow engineering", "AI product engineering"],
        strengths=["AI systems"],
        target_roles=["AI Engineer"],
    ))
    job = service.create_job({
        "title": "AI Engineer",
        "company": "Northstar Labs",
        "description": "Build Python LLM agents and RAG systems.",
    })
    target = service.create_target({
        "name": "Sarah Chen",
        "title": "Hiring Manager",
        "company": "Northstar Labs",
        "email": "sarah@example.com",
    })

    prepared = service.prepare_outreach(target["id"], job["id"])
    outreach_id = prepared["outreach_id"]
    assert service.db.get_outreach(outreach_id)["status"] == "PENDING_APPROVAL"
    assert service.db.validate_approval_token(prepared["approval_token"])

    decision = service.decide(prepared["approval_token"], "approve")
    assert decision["status"] == "APPROVED"
    # Approving sends that one message immediately.
    assert decision["delivery"]["status"] == "SENT"
    assert service.db.get_outreach(outreach_id)["status"] == "SENT"
    assert service.db.get_target(target["id"])["already_contacted"] is True
