from reachai.storage.database import Database
from reachai.workers import ApprovalWorker, SendWorker
from datetime import datetime, timezone


def test_cli_to_approval_to_send_workflow(tmp_path):
    """Test the full workflow: CLI creates outreach → approval email → send"""
    db = Database(str(tmp_path / "reachai.db"))
    
    # Step 1: CLI creates an outreach in PENDING_APPROVAL state
    outreach_id = "outreach-test-1"
    db.save_outreach({
        "id": outreach_id,
        "target_id": "target-1",
        "channel": "email",
        "subject": "AI Engineer opportunity",
        "message": "Hi Sarah, I'd love to connect...",
        "match_score": 92.0,
        "status": "PENDING_APPROVAL",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    
    # Step 2: Create an approval token for this outreach
    token = db.create_approval_token(outreach_id)
    assert db.validate_approval_token(token) is True
    assert db.get_outreach(outreach_id)["status"] == "PENDING_APPROVAL"
    
    # Step 3: User sends approval email reply with token
    approval_worker = ApprovalWorker(store=db)
    decision = approval_worker.process_email({
        "from": "aman@example.com",
        "body": f"APPROVE {token}",
    })
    assert decision["action"] == "APPROVED"
    assert db.get_outreach(outreach_id)["status"] == "APPROVED"
    
    # Step 4: Send worker processes all approved outreach
    send_worker = SendWorker(store=db)
    results = send_worker.process_pending()
    assert len(results) == 1
    assert results[0]["outreach_id"] == outreach_id
    assert results[0]["status"] == "SENT"
    
    # Step 5: Status should now show sent=1, pending_approval=0
    assert db.get_outreach(outreach_id)["status"] == "SENT"
    
    # Step 6: No more pending work to send
    assert send_worker.process_pending() == []
