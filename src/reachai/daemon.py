"""
ReachAI background daemon for approval processing and sending.

Every poll it applies APPROVE/REJECT replies and sends approved outreach;
once a day it finds new people via Apollo and emails drafts for approval.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict

from reachai.integrations.gmail import GmailClient
from reachai.scheduler.approval_loop import ApprovalLoop
from reachai.storage.database import Database
from reachai.workers import SendWorker


class ReachAIDaemon:
    """Background daemon for approval processing and sending."""

    def __init__(self, db_path: str | None = None, approval_poll_interval: int = 60, send_interval: int = 300):
        self.db = Database(db_path)
        self.db_path = str(self.db.db_path)
        self.gmail_client = GmailClient()
        self.approval_loop = ApprovalLoop(gmail_client=self.gmail_client, db=self.db)
        self.send_worker = SendWorker(store=self.db)
        
        self.approval_poll_interval = approval_poll_interval  # Check emails every 60 seconds
        self.send_interval = send_interval  # Send pending every 5 minutes
        
        self.running = False
        self.last_send_time = 0
        
        # PID file for daemon management
        self.pid_file = Path(".reachai_daemon.pid")

    def setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(sig, frame):
            print("\n[ReachAI Daemon] Received signal, shutting down...")
            self.running = False
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def write_pid(self) -> None:
        """Write daemon PID to file."""
        with open(self.pid_file, "w") as f:
            f.write(str(os.getpid()))

    def remove_pid(self) -> None:
        """Remove PID file."""
        if self.pid_file.exists():
            self.pid_file.unlink()

    def read_pid(self) -> int | None:
        """Read PID from file if it exists."""
        if self.pid_file.exists():
            with open(self.pid_file, "r") as f:
                try:
                    return int(f.read().strip())
                except ValueError:
                    return None
        return None

    def is_running(self) -> bool:
        """Check if daemon is running."""
        pid = self.read_pid()
        if pid is None:
            return False
        try:
            os.kill(pid, 0)  # Signal 0 checks if process exists
            return True
        except OSError:
            return False

    def run(self) -> None:
        """Run the daemon loop: replies and sends every poll, discovery once a day."""
        from reachai.service import ReachAIService, WorkflowError

        service = ReachAIService(db=self.db)
        self.running = True
        self.setup_signal_handlers()
        self.write_pid()

        print(f"[ReachAI Daemon] Starting (PID {os.getpid()})")
        print(f"[ReachAI Daemon] Reply poll interval: {self.approval_poll_interval}s")
        last_cycle_day = None

        try:
            while self.running:
                today = time.strftime("%Y-%m-%d")
                if today != last_cycle_day and service.apollo.configured() and service.gmail.authorized():
                    try:
                        summary = service.run_cycle(find=True)
                        found = summary.get("found") or {}
                        print(f"[ReachAI Daemon] Found {len(found.get('added', []))} people; "
                              f"emailed {len(summary['drafted'])} drafts for approval")
                        if found.get("error"):
                            print(f"[ReachAI Daemon] Apollo: {found['error']}")
                    except WorkflowError as e:
                        print(f"[ReachAI Daemon] Discovery skipped: {e}")
                    last_cycle_day = today

                try:
                    for decision in service.process_replies():
                        delivery = (decision.get("delivery") or {}).get("status", "")
                        print(f"  {decision['action']}: {decision.get('token', '')} {delivery}")
                except Exception as e:
                    print(f"[ReachAI Daemon] Error processing replies: {e}")

                try:
                    for result in service.send_approved():
                        print(f"  ✓ Sent: {result['outreach_id']}")
                except Exception as e:
                    print(f"[ReachAI Daemon] Error sending outreach: {e}")

                time.sleep(self.approval_poll_interval)
        finally:
            self.remove_pid()
            print("[ReachAI Daemon] Stopped")

    def start(self) -> Dict[str, Any]:
        """Start the daemon."""
        if self.is_running():
            pid = self.read_pid()
            return {"status": "already_running", "pid": pid}
        
        # For now, run in foreground (can be daemonized later with python-daemon)
        self.run()
        return {"status": "started"}

    def stop(self) -> Dict[str, Any]:
        """Stop the daemon."""
        pid = self.read_pid()
        if pid is None:
            return {"status": "not_running"}
        
        try:
            os.kill(pid, signal.SIGTERM)
            # Wait for daemon to shut down
            time.sleep(1)
            if self.is_running():
                return {"status": "stop_failed", "pid": pid}
            return {"status": "stopped", "pid": pid}
        except OSError:
            return {"status": "not_running"}

    def status(self) -> Dict[str, Any]:
        """Get daemon status."""
        pid = self.read_pid()
        running = self.is_running()
        
        stats = {
            "status": "running" if running else "stopped",
            "pid": pid,
        }
        
        if running and pid:
            try:
                # Get outreach counts from database
                with self.db._connect() as conn:
                    all_outreach = conn.execute("SELECT status FROM outreach").fetchall()
                    status_counts = {}
                    for row in all_outreach:
                        status = row["status"]
                        status_counts[status] = status_counts.get(status, 0) + 1
                
                stats["outreach_stats"] = {
                    "pending_approval": status_counts.get("PENDING_APPROVAL", 0),
                    "approved": status_counts.get("APPROVED", 0),
                    "sent": status_counts.get("SENT", 0),
                    "rejected": status_counts.get("REJECTED", 0),
                }
            except Exception as e:
                stats["error"] = str(e)
        
        return stats
