from reachai.cli import cmd_discover, cmd_rank, cmd_outreach
from reachai.storage.database import Database


def test_discover_rank_outreach_workflow(tmp_path):
    db = Database(str(tmp_path / "flow.db"))
    db.save_job({
        "job_id": "job-1",
        "title": "AI Engineer",
        "company": "Northstar Labs",
        "location": "Remote",
        "url": "https://example.com/jobs/ai-engineer",
        "source": "local_db",
        "description": "Python, AI agents, LLM workflows, RAG systems",
    })
    db.save_target({
        "target_id": "target-1",
        "name": "Sarah Chen",
        "title": "Hiring Manager",
        "company": "Northstar Labs",
        "email": "sarah@northstar.ai",
        "source": "csv_import",
        "status": "DISCOVERED",
    })

    discovered = cmd_discover(str(tmp_path / "flow.db"))
    assert discovered["status"] == "discover_complete"
    assert len(discovered["jobs"]) >= 1

    ranked = cmd_rank(str(tmp_path / "flow.db"), keywords=["AI", "engineer"])
    assert ranked["status"] == "rank_complete"
    assert ranked["jobs"][0]["score"] >= ranked["jobs"][-1]["score"]

    outreach = cmd_outreach(str(tmp_path / "flow.db"), target_id="target-1")
    assert outreach["status"] == "outreach_ready"
    assert outreach["persistent"] is True
    assert outreach["outreach_id"]
