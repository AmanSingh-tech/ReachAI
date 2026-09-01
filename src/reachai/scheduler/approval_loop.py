from __future__ import annotations

import time
from typing import Any, Dict, List

from reachai.integrations.gmail import GmailClient
from reachai.storage.database import Database
from reachai.workers import ApprovalWorker


class ApprovalLoop:
    """Background approval processing loop that polls Gmail and processes approval decisions."""

    def __init__(self, gmail_client: GmailClient | None = None, db: Database | None = None):
        self.gmail_client = gmail_client or GmailClient()
        self.db = db or Database()
        self.worker = ApprovalWorker(store=self.db)
        self.processed_message_ids = set()

    def run(self, poll_interval_seconds: int = 60, max_iterations: int | None = None) -> Dict[str, Any]:
        """
        Run the approval polling loop.

        Args:
            poll_interval_seconds: How often to check for new emails
            max_iterations: For testing; run this many times then exit (None = infinite)

        Returns:
            Final summary of processed approvals
        """
        iterations = 0
        total_approved = 0
        total_rejected = 0

        while True:
            try:
                messages = self.gmail_client.get_new_messages(query="is:unread subject:ReachAI")
                decisions = []

                for message in messages:
                    if message.get("id") in self.processed_message_ids:
                        continue

                    decision = self.worker.process_email(message)
                    decisions.append(decision)

                    if decision["action"] == "APPROVED":
                        total_approved += 1
                    elif decision["action"] == "REJECTED":
                        total_rejected += 1

                    # Mark as read to avoid reprocessing
                    message_id = message.get("id")
                    if message_id:
                        self.processed_message_ids.add(message_id)
                        self.gmail_client.mark_as_read(message_id)

                iterations += 1
                if max_iterations and iterations >= max_iterations:
                    break

                time.sleep(poll_interval_seconds)

            except Exception as e:
                return {
                    "status": "error",
                    "error": str(e),
                    "approved": total_approved,
                    "rejected": total_rejected,
                }

        return {
            "status": "completed",
            "approved": total_approved,
            "rejected": total_rejected,
            "iterations": iterations,
        }
