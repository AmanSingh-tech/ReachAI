from reachai.integrations.gmail import GmailClient
from reachai.scheduler.approval_loop import ApprovalLoop
from reachai.storage.database import Database
from datetime import datetime, timezone


def test_approval_loop_polls_and_processes_approval_email(tmp_path):
    """Test that ApprovalLoop polls Gmail and processes approval decisions."""
    db = Database(str(tmp_path / "reachai.db"))
    
    # Create an outreach in the database
    outreach_id = "outreach-test-1"
    db.save_outreach({
        "id": outreach_id,
        "target_id": "target-1",
        "channel": "email",
        "subject": "AI Engineer opportunity",
        "message": "Hi Sarah...",
        "match_score": 92.0,
        "status": "PENDING_APPROVAL",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    
    # Create approval token
    token = db.create_approval_token(outreach_id)
    
    # Create a mock Gmail client with a test message
    gmail = GmailClient()
    gmail._add_message_for_testing({
        "id": "msg-1",
        "from": "aman@example.com",
        "subject": f"Re: [ReachAI] Approval required — Sarah Chen",
        "body": f"APPROVE {token}",
    })
    
    # Override get_new_messages to return our test message
    gmail.get_new_messages = lambda query="": gmail.message_history
    
    # Create and run the approval loop
    loop = ApprovalLoop(gmail_client=gmail, db=db)
    result = loop.run(poll_interval_seconds=0, max_iterations=1)
    
    # Verify the loop processed the approval
    assert result["status"] == "completed"
    assert result["approved"] == 1
    assert result["rejected"] == 0
    assert result["iterations"] == 1
    
    # Verify the outreach status changed to APPROVED
    outreach = db.get_outreach(outreach_id)
    assert outreach["status"] == "APPROVED"


def test_approval_loop_rejects_invalid_tokens(tmp_path):
    """Test that ApprovalLoop handles rejection of invalid tokens."""
    db = Database(str(tmp_path / "reachai.db"))
    
    # Create an outreach
    outreach_id = "outreach-test-2"
    db.save_outreach({
        "id": outreach_id,
        "target_id": "target-2",
        "channel": "email",
        "subject": "ML Engineer opportunity",
        "message": "Hi Alex...",
        "match_score": 85.0,
        "status": "PENDING_APPROVAL",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    
    # Create a Gmail with an email containing an invalid token
    gmail = GmailClient()
    gmail._add_message_for_testing({
        "id": "msg-2",
        "from": "aman@example.com",
        "body": "APPROVE invalid_token_xyz",
    })
    gmail.get_new_messages = lambda query="": gmail.message_history
    
    # Run the loop
    loop = ApprovalLoop(gmail_client=gmail, db=db)
    result = loop.run(poll_interval_seconds=0, max_iterations=1)
    
    # Loop should still complete without error
    assert result["status"] == "completed"
    assert result["approved"] == 0


def test_approval_loop_avoids_reprocessing_messages(tmp_path):
    """Test that ApprovalLoop doesn't reprocess the same message twice."""
    db = Database(str(tmp_path / "reachai.db"))
    
    # Create an outreach and token
    outreach_id = "outreach-test-3"
    db.save_outreach({
        "id": outreach_id,
        "target_id": "target-3",
        "channel": "email",
        "subject": "Test",
        "message": "Message",
        "match_score": 75.0,
        "status": "PENDING_APPROVAL",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    token = db.create_approval_token(outreach_id)
    
    # Gmail with a test message
    gmail = GmailClient()
    gmail._add_message_for_testing({
        "id": "msg-3",
        "from": "user@example.com",
        "body": f"APPROVE {token}",
    })
    gmail.get_new_messages = lambda query="": gmail.message_history
    
    # Run twice
    loop = ApprovalLoop(gmail_client=gmail, db=db)
    result1 = loop.run(poll_interval_seconds=0, max_iterations=1)
    result2 = loop.run(poll_interval_seconds=0, max_iterations=1)
    
    # First run processes it, second run sees it's already processed
    assert result1["approved"] == 1
    assert result2["approved"] == 0  # No new messages since we already processed msg-3
