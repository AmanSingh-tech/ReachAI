"""Integration test for CSV import -> orchestrator -> approval workflow."""
import json
import uuid
from pathlib import Path
from reachai.skills.ingestion import CSVIngestionSkill
from reachai.agents.orchestrator import ReachAIOrchestrator
from reachai.models.candidate import CandidateProfile
from reachai.storage.database import Database


def test_csv_import_to_outreach_workflow(tmp_path, monkeypatch):
    """Test complete workflow: CSV import -> orchestrator -> approval."""
    # Setup test environment
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-12345")
    
    db_path = str(tmp_path / "test.db")
    db = Database(db_path)
    
    # Create test CSV files
    targets_csv = tmp_path / "targets.csv"
    targets_csv.write_text(
        "name,title,company,email\n"
        "Sarah Chen,Hiring Manager,Northstar Labs,sarah@northstar.ai\n"
    )
    
    # Step 1: Ingest targets
    ingestion = CSVIngestionSkill(db=db)
    result = ingestion.ingest_targets(str(targets_csv))
    
    assert result["status"] == "success"
    assert result["loaded"] == 1
    
    # Step 2: Get imported target
    targets = ingestion.list_targets()
    assert len(targets) == 1
    target = targets[0]
    assert target["name"] == "Sarah Chen"
    
    # Step 3: Create candidate profile
    candidate = CandidateProfile(
        name="Aman Singh",
        title="AI Engineer",
        background="Expert in LLM systems and outreach automation",
        key_achievements=["Shipped 10+ AI products", "Led ML teams"],
        current_role="Founder",
    )
    
    # Step 4: Run orchestrator with imported target
    from reachai.models.target import TargetProfile
    target_profile = TargetProfile(
        target_id=target["id"],
        name=target["name"],
        title=target["title"],
        company=target["company"],
        email=target["email"],
    )
    
    orchestrator = ReachAIOrchestrator()
    result = orchestrator.run(candidate, target_profile)
    
    # Verify orchestrator output
    assert result["eligible"] is True
    assert "draft" in result
    assert "score" in result
    assert "critic" in result
    
    # Step 5: Simulate saving outreach to database
    # In real workflow, CLI would save this after orchestration
    import uuid
    outreach_record = {
        "id": str(uuid.uuid4()),
        "target_id": target["id"],
        "candidate_name": candidate.name,
        "draft": result["draft"],
        "status": "PENDING_APPROVAL",
    }
    saved = db.save_outreach(outreach_record)
    assert saved["status"] == "PENDING_APPROVAL"
    
    # Step 6: Verify outreach was saved
    outreach_records = db.list_outreach("PENDING_APPROVAL")
    assert len(outreach_records) > 0
    
    outreach = outreach_records[0]
    assert outreach["target_id"] == target["id"]
    assert outreach["status"] == "PENDING_APPROVAL"


def test_csv_import_with_invalid_rows(tmp_path):
    """Test that invalid CSV rows are skipped gracefully."""
    targets_csv = tmp_path / "targets.csv"
    targets_csv.write_text(
        "name,title,company,email\n"
        "Sarah Chen,Hiring Manager,Northstar Labs,sarah@northstar.ai\n"
        ",,invalid row,\n"
        "Alex,Engineer,SignalForge,alex@signal.io\n"
    )
    
    db_path = str(tmp_path / "test.db")
    db = Database(db_path)
    ingestion = CSVIngestionSkill(db=db)
    
    result = ingestion.ingest_targets(str(targets_csv))
    
    assert result["status"] == "success"
    assert result["loaded"] == 2  # Only valid rows
    assert result["skipped"] == 1
    
    targets = ingestion.list_targets()
    assert len(targets) == 2


def test_list_targets_by_status(tmp_path):
    """Test filtering targets by status."""
    db_path = str(tmp_path / "test.db")
    db = Database(db_path)
    
    # Save targets with different statuses
    db.save_target({
        "target_id": "t1",
        "name": "Target 1",
        "company": "Company A",
        "status": "DISCOVERED",
    })
    db.save_target({
        "target_id": "t2",
        "name": "Target 2",
        "company": "Company B",
        "status": "OUTREACH_SENT",
    })
    
    ingestion = CSVIngestionSkill(db=db)
    
    discovered = ingestion.list_targets(status="DISCOVERED")
    assert len(discovered) == 1
    assert discovered[0]["name"] == "Target 1"
    
    sent = ingestion.list_targets(status="OUTREACH_SENT")
    assert len(sent) == 1
    assert sent[0]["name"] == "Target 2"
