from reachai.integrations.gmail import GmailClient
from reachai.scheduler.approval_loop import ApprovalLoop
from reachai.storage.database import Database
from reachai.workers import SendWorker
from datetime import datetime, timezone


def test_full_workflow_approval_to_send(tmp_path):
    """Test complete workflow: create outreach → approve via email → send."""
    db = Database(str(tmp_path / "reachai.db"))
    
    # Step 1: Create outreach (simulating CLI cmd_outreach)
    outreach_id = "outreach-full-workflow"
    db.save_outreach({
        "id": outreach_id,
        "target_id": "sarah-chen",
        "channel": "email",
        "subject": "AI Engineer opportunity at Northstar Labs",
        "message": "Hi Sarah,\n\nI noticed you're hiring for AI and product-focused work...",
        "match_score": 92.0,
        "status": "PENDING_APPROVAL",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    
    # Verify it starts in PENDING_APPROVAL
    assert db.get_outreach(outreach_id)["status"] == "PENDING_APPROVAL"
    
    # Step 2: Create approval token
    token = db.create_approval_token(outreach_id)
    
    # Step 3: Simulate user replying to approval email (Gmail polling)
    gmail = GmailClient()
    gmail._add_message_for_testing({
        "id": "msg-approval-1",
        "from": "aman@example.com",
        "subject": "[ReachAI] Approval required — Sarah Chen",
        "body": f"APPROVE {token}",
    })
    gmail.get_new_messages = lambda query="": gmail.message_history
    
    # Step 4: Run approval loop (processes email reply)
    approval_loop = ApprovalLoop(gmail_client=gmail, db=db)
    approval_result = approval_loop.run(poll_interval_seconds=0, max_iterations=1)
    
    assert approval_result["status"] == "completed"
    assert approval_result["approved"] == 1
    assert db.get_outreach(outreach_id)["status"] == "APPROVED"
    
    # Step 5: Run send worker (sends all approved outreach)
    send_worker = SendWorker(store=db)
    send_result = send_worker.process_pending()
    
    assert len(send_result) == 1
    assert send_result[0]["outreach_id"] == outreach_id
    assert send_result[0]["status"] == "SENT"
    
    # Step 6: Verify final status
    assert db.get_outreach(outreach_id)["status"] == "SENT"
    
    # Step 7: Verify no more pending work
    assert send_worker.process_pending() == []
