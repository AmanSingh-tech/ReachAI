from reachai.storage.database import Database
from reachai.workers import ApprovalWorker, SendWorker


def test_database_tracks_approval_tokens_and_outreach_state(tmp_path):
    db = Database(str(tmp_path / "reachai.db"))

    db.save_outreach({
        "outreach_id": "draft-1",
        "target_id": "target-1",
        "channel": "email",
        "subject": "Intro",
        "message": "Hi Sarah",
        "match_score": 92.0,
        "status": "PENDING_APPROVAL",
        "created_at": "2025-01-01T00:00:00",
    })

    token = db.create_approval_token("draft-1")

    assert db.validate_approval_token(token) is True
    assert db.get_outreach("draft-1")["status"] == "PENDING_APPROVAL"

    assert db.approve_token(token) is True
    assert db.get_outreach("draft-1")["status"] == "APPROVED"
    assert db.validate_approval_token(token) is False


def test_src_workers_process_approval_email_and_send_only_approved_outreach(tmp_path):
    db = Database(str(tmp_path / "reachai.db"))
    db.save_outreach({
        "outreach_id": "draft-1",
        "target_id": "target-1",
        "channel": "email",
        "subject": "Intro",
        "message": "Hi Sarah",
        "match_score": 92.0,
        "status": "PENDING_APPROVAL",
        "created_at": "2025-01-01T00:00:00",
    })
    token = db.create_approval_token("draft-1")

    decision = ApprovalWorker(store=db).process_email({"body": f"APPROVE {token}"})
    assert decision["action"] == "APPROVED"
    assert db.get_outreach("draft-1")["status"] == "APPROVED"

    sent = SendWorker(store=db).process_pending()
    assert sent == [{"outreach_id": "draft-1", "status": "SENT"}]
    assert SendWorker(store=db).process_pending() == []
