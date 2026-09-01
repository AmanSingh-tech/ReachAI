from pathlib import Path

from reachai.reporting import ReportGenerator
from reachai.skills.discovery import DiscoverySkill
from reachai.storage.database import Database


def test_discovery_skill_reads_local_jobs(tmp_path):
    db = Database(str(tmp_path / "jobs.db"))
    db.save_job({
        "job_id": "local-1",
        "title": "AI Engineer",
        "company": "Northstar Labs",
        "location": "Remote",
        "url": "https://example.com/jobs/ai-engineer",
        "source": "local_db",
    })

    discovery = DiscoverySkill(db=db)
    results = discovery.discover({"keywords": ["AI", "engineer"]})

    assert len(results) >= 1
    assert any(item["title"] == "AI Engineer" for item in results)
    assert any(item["source"] == "local_db" for item in results)


def test_report_generator_writes_summary(tmp_path):
    report_dir = tmp_path / "reports"
    generator = ReportGenerator(output_dir=str(report_dir))

    path = generator.build({
        "jobs_discovered": 5,
        "pending_approval": 2,
        "approved": 3,
        "sent": 1,
    })

    file_path = Path(path)
    assert file_path.exists()
    html = file_path.read_text(encoding="utf-8")
    assert "Jobs discovered: 5" in html
    assert "Pending approval: 2" in html
