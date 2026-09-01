#!/usr/bin/env python3
"""
ReachAI end-to-end workflow demonstration.

This script shows the complete workflow:
1. Setup: Initialize candidate profile
2. Outreach: Generate and save an approval-ready draft
3. Approval: Simulate email reply and process approval
4. Send: Process approved messages
5. Status: Show final state
"""

import json
import sys
from datetime import datetime, timezone

from reachai.agents.orchestrator import ReachAIOrchestrator
from reachai.config import get_settings
from reachai.integrations.gmail import GmailClient
from reachai.models.candidate import CandidateProfile
from reachai.models.target import TargetProfile
from reachai.scheduler.approval_loop import ApprovalLoop
from reachai.storage.database import Database
from reachai.workers import SendWorker


def print_section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def workflow():
    db = Database()
    settings = get_settings()

    # Step 1: Setup
    print_section("STEP 1: Setup")
    candidate = CandidateProfile(
        name="Aman Kumar Singh",
        email="pendulum4441@gmail.com",
        resume_url="https://example.com/resume",
        skills=["Python", "LLMs", "RAG", "AI Agents", "Next.js", "Node.js"],
        experience=["LLM workflows", "AI product engineering", "full-stack product work"],
        strengths=["AI systems", "agentic workflows", "MLOps"],
        target_roles=["AI Engineer", "Applied AI Engineer", "ML Engineer"],
    )
    print(f"✓ Candidate: {candidate.name}")
    print(f"✓ Email: {candidate.email}")
    print(f"✓ Target roles: {', '.join(candidate.target_roles)}")
    print(f"✓ Daily limit: {settings.daily_limit} messages/day")

    # Step 2: Outreach generation
    print_section("STEP 2: Generate Outreach Draft")
    target = TargetProfile(
        name="Sarah Chen",
        title="Hiring Manager",
        company="Northstar Labs",
        linkedin_url="https://linkedin.com/in/sarah-chen",
        source="cli_demo",
    )
    print(f"✓ Target: {target.name} ({target.title})")
    print(f"✓ Company: {target.company}")

    orchestrator = ReachAIOrchestrator()
    result = orchestrator.run(candidate, target)

    if not result.get("eligible"):
        print("✗ Target not eligible for outreach")
        return

    print(f"✓ Eligibility: PASS")
    print(f"✓ Match score: {result.get('score')}/100")
    print(f"✓ Critic status: {result.get('critic', {}).get('passed')}")

    # Save to database
    outreach_id = f"demo-{datetime.now(timezone.utc).timestamp()}"
    draft = result.get("draft", {})
    db.save_outreach({
        "id": outreach_id,
        "target_id": target.name.lower(),
        "channel": "email",
        "subject": draft.get("subject", "Intro"),
        "message": draft.get("message", ""),
        "match_score": result.get("score", 0),
        "status": "PENDING_APPROVAL",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Create approval token for this outreach
    approval_token = db.create_approval_token(outreach_id)

    print(f"✓ Outreach ID: {outreach_id}")
    print(f"✓ Status: PENDING_APPROVAL")
    print(f"✓ Approval token: {approval_token}")
    print(f"\nDraft message:")
    print(f"-" * 60)
    print(draft.get("message", ""))
    print(f"-" * 60)

    # Step 3: Simulate approval email
    print_section("STEP 3: Simulate Approval Email Reply")
    gmail = GmailClient()
    gmail._add_message_for_testing({
        "id": f"msg-{outreach_id}",
        "from": candidate.email,
        "subject": f"Re: [ReachAI] Approval required — {target.name}",
        "body": f"APPROVE {approval_token}",
    })
    
    # Override the get_new_messages to return test messages
    original_get_new_messages = gmail.get_new_messages
    def mock_get_new_messages(query=""):
        return gmail.message_history
    gmail.get_new_messages = mock_get_new_messages

    print(f"✓ Simulated email from {candidate.email}")
    print(f"✓ Body: APPROVE {approval_token}")

    # Step 4: Process approval email
    print_section("STEP 4: Process Approval via ApprovalLoop")
    approval_loop = ApprovalLoop(gmail_client=gmail, db=db)
    approval_result = approval_loop.run(poll_interval_seconds=0, max_iterations=1)

    print(f"✓ Approval processing result: {approval_result['status']}")
    print(f"✓ Approved: {approval_result['approved']}")
    print(f"✓ Rejected: {approval_result['rejected']}")

    outreach = db.get_outreach(outreach_id)
    print(f"✓ Outreach status: {outreach['status']}")

    # Step 5: Send approved messages
    print_section("STEP 5: Send Approved Outreach")
    send_worker = SendWorker(store=db)
    send_results = send_worker.process_pending()

    for result in send_results:
        print(f"✓ Sent: {result['outreach_id']}")

    outreach = db.get_outreach(outreach_id)
    print(f"✓ Final outreach status: {outreach['status']}")

    # Step 6: Status
    print_section("STEP 6: Final Status")
    with db._connect() as conn:
        all_outreach = conn.execute("SELECT status FROM outreach").fetchall()
        status_counts = {}
        for row in all_outreach:
            status = row["status"]
            status_counts[status] = status_counts.get(status, 0) + 1

    sent_today = db.count_sent_today()
    print(f"✓ Total targets: {len(all_outreach)}")
    print(f"✓ Pending approval: {status_counts.get('PENDING_APPROVAL', 0)}")
    print(f"✓ Approved: {status_counts.get('APPROVED', 0)}")
    print(f"✓ Sent: {status_counts.get('SENT', 0)}")
    print(f"✓ Rejected: {status_counts.get('REJECTED', 0)}")
    print(f"✓ Sent today: {sent_today}/{settings.daily_limit}")

    print_section("✓ Workflow Complete")


if __name__ == "__main__":
    try:
        workflow()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
