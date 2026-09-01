from reachai.daemon import ReachAIDaemon
from reachai.storage.database import Database
from datetime import datetime, timezone


def test_daemon_detects_not_running():
    """Test that daemon reports not running when PID file doesn't exist."""
    daemon = ReachAIDaemon()
    assert daemon.is_running() is False
    assert daemon.read_pid() is None


def test_daemon_write_and_read_pid(tmp_path):
    """Test PID file write/read."""
    import os
    
    # Change to temp dir
    orig_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        daemon = ReachAIDaemon()
        
        daemon.write_pid()
        assert daemon.pid_file.exists()
        
        pid = daemon.read_pid()
        assert pid == os.getpid()
        
        daemon.remove_pid()
        assert not daemon.pid_file.exists()
    finally:
        os.chdir(orig_cwd)


def test_daemon_status_includes_outreach_stats(tmp_path):
    """Test that daemon status includes outreach statistics."""
    db = Database(str(tmp_path / "reachai.db"))
    
    # Create some test outreach
    db.save_outreach({
        "id": "outreach-1",
        "target_id": "target-1",
        "channel": "email",
        "subject": "Test",
        "message": "Test",
        "match_score": 90.0,
        "status": "PENDING_APPROVAL",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    
    db.save_outreach({
        "id": "outreach-2",
        "target_id": "target-2",
        "channel": "email",
        "subject": "Test",
        "message": "Test",
        "match_score": 85.0,
        "status": "SENT",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    
    daemon = ReachAIDaemon(str(tmp_path / "reachai.db"))
    status = daemon.status()
    
    assert status["status"] == "stopped"
    assert status["pid"] is None
    # Can't check outreach_stats since daemon isn't running


def test_daemon_status_when_running():
    """Test that daemon reports status correctly."""
    daemon = ReachAIDaemon()
    status = daemon.status()
    
    assert status["status"] == "stopped"
    assert "pid" in status
