from pathlib import Path
from reachai.skills.ingestion import CSVIngestionSkill
from reachai.storage.database import Database


def test_ingest_targets_from_csv(tmp_path):
    """Test ingesting targets from CSV file."""
    # Create a sample CSV
    csv_file = tmp_path / "targets.csv"
    csv_file.write_text(
        "name,title,company,linkedin_url,email,source\n"
        "Sarah Chen,Hiring Manager,Northstar Labs,https://linkedin.com/in/sarah,sarah@northstar.ai,csv\n"
        "Alex Rodriguez,Engineer,SignalForge,https://linkedin.com/in/alex,alex@signal.io,csv\n"
    )
    
    db = Database(str(tmp_path / "test.db"))
    ingestion = CSVIngestionSkill(db=db)
    
    result = ingestion.ingest_targets(str(csv_file))
    
    assert result["status"] == "success"
    assert result["loaded"] == 2
    assert result["skipped"] == 0
    
    targets = ingestion.list_targets()
    assert len(targets) == 2
    names = {t["name"] for t in targets}
    assert "Sarah Chen" in names
    assert "Alex Rodriguez" in names


def test_ingest_jobs_from_csv(tmp_path):
    """Test ingesting jobs from CSV file."""
    csv_file = tmp_path / "jobs.csv"
    csv_file.write_text(
        "title,company,location,url,source\n"
        "AI Engineer,Northstar Labs,SF,https://northstar.ai/jobs,csv\n"
        "ML Engineer,SignalForge,Remote,https://signal.io/jobs,csv\n"
    )
    
    db = Database(str(tmp_path / "test.db"))
    ingestion = CSVIngestionSkill(db=db)
    
    result = ingestion.ingest_jobs(str(csv_file))
    
    assert result["status"] == "success"
    assert result["loaded"] == 2
    assert result["skipped"] == 0
    
    jobs = ingestion.list_jobs()
    assert len(jobs) == 2
    titles = {j["title"] for j in jobs}
    assert "AI Engineer" in titles
    assert "ML Engineer" in titles


def test_ingest_skips_missing_required_fields(tmp_path):
    """Test that ingestion skips rows with missing required fields."""
    csv_file = tmp_path / "targets.csv"
    csv_file.write_text(
        "name,title,company\n"
        "Sarah Chen,Hiring Manager,Northstar Labs\n"
        "Missing Company,,\n"
        "Alex,Engineer,SignalForge\n"
    )
    
    db = Database(str(tmp_path / "test.db"))
    ingestion = CSVIngestionSkill(db=db)
    
    result = ingestion.ingest_targets(str(csv_file))
    
    assert result["status"] == "success"
    assert result["loaded"] == 2
    assert result["skipped"] == 1  # Row with missing company


def test_ingest_handles_missing_file():
    """Test that ingestion handles missing files gracefully."""
    ingestion = CSVIngestionSkill()
    
    result = ingestion.ingest_targets("/nonexistent/targets.csv")
    
    assert result["status"] == "error"
    assert "not found" in result["error"].lower()


def test_database_save_and_list_targets(tmp_path):
    """Test database target persistence."""
    db = Database(str(tmp_path / "test.db"))
    
    # Save a target
    db.save_target({
        "target_id": "target-1",
        "name": "Test Person",
        "title": "Manager",
        "company": "Test Co",
        "source": "test",
        "status": "DISCOVERED",
    })
    
    # Retrieve it
    targets = db.list_targets()
    assert len(targets) == 1
    assert targets[0]["name"] == "Test Person"
    
    # Get specific target
    target = db.get_target("target-1")
    assert target["name"] == "Test Person"
    assert target["company"] == "Test Co"


def test_database_save_and_list_jobs(tmp_path):
    """Test database job persistence."""
    db = Database(str(tmp_path / "test.db"))
    
    # Save a job
    db.save_job({
        "job_id": "job-1",
        "title": "AI Engineer",
        "company": "Test Co",
        "url": "https://example.com",
        "source": "test",
    })
    
    # List jobs
    jobs = db.list_jobs()
    assert len(jobs) == 1
    assert jobs[0]["title"] == "AI Engineer"
    
    # Get specific job
    job = db.get_job("job-1")
    assert job["title"] == "AI Engineer"
