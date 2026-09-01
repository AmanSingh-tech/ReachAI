from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from reachai.agents.orchestrator import ReachAIOrchestrator
from reachai.config import get_settings
from reachai.daemon import ReachAIDaemon
from reachai.models.candidate import CandidateProfile
from reachai.models.target import TargetProfile
from reachai.reporting import ReportGenerator
from reachai.skills.discovery import DiscoverySkill
from reachai.skills.ingestion import CSVIngestionSkill
from reachai.skills.scoring import ScoringSkill
from reachai.storage.database import Database


def build_candidate() -> CandidateProfile:
    return CandidateProfile(
        name="Aman Kumar Singh",
        email="aman@example.com",
        resume_url="https://example.com/resume",
        skills=["Python", "LLMs", "RAG", "AI Agents", "Next.js", "Node.js"],
        experience=["LLM workflows", "AI product engineering", "full-stack product work"],
        strengths=["AI systems", "agentic workflows", "MLOps"],
        target_roles=["AI Engineer", "Applied AI Engineer", "ML Engineer"],
    )


def build_target(name: str, company: str, title: str = "Hiring Manager") -> TargetProfile:
    return TargetProfile(
        name=name,
        title=title,
        company=company,
        linkedin_url="https://linkedin.com/in/example",
        source="cli",
    )


def cmd_setup() -> dict:
    return {"status": "setup_complete", "candidate": build_candidate().model_dump()}


def cmd_discover(db_path: str = "data/reachai.db", keywords: list[str] | None = None) -> dict:
    db = Database(db_path)
    skill = DiscoverySkill(db=db)
    discovered = skill.discover({"keywords": keywords or ["AI", "engineer", "ML", "LLM"]})
    return {"status": "discover_complete", "jobs": discovered}


def cmd_rank(db_path: str = "data/reachai.db", *, keywords: list[str] | None = None, limit: int = 10) -> dict:
    db = Database(db_path)
    jobs = cmd_discover(db_path, keywords or ["AI", "engineer", "ML", "LLM"])["jobs"]
    candidate = build_candidate()
    scorer = ScoringSkill()
    ranked = []
    for job in jobs:
        description = str(job.get("description") or "")
        extras = [
            str(job.get("company") or ""),
            str(job.get("source") or ""),
            str(job.get("location") or ""),
        ]
        job_payload = {
            "title": job.get("title", ""),
            "description": description + " " + " ".join(filter(None, extras)),
        }
        score = scorer.score_job(job_payload, candidate.model_dump())
        ranked.append({
            "job_id": job.get("job_id"),
            "title": job.get("title"),
            "company": job.get("company"),
            "location": job.get("location"),
            "url": job.get("url"),
            "source": job.get("source"),
            "score": int(score),
        })
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return {"status": "rank_complete", "jobs": ranked[:limit]}


def cmd_outreach(db_path: str = "data/reachai.db", *, target_id: str | None = None, target_name: str = "Sarah Chen", target_company: str = "Northstar Labs") -> dict:
    db = Database(db_path)
    settings = get_settings()
    orchestrator = ReachAIOrchestrator()
    candidate = build_candidate()

    if target_id:
        target_record = db.get_target(target_id)
        if not target_record:
            return {"status": "target_not_found", "target_id": target_id}
        target = TargetProfile(
            target_id=target_record.get("id", target_id),
            name=target_record.get("name", target_name),
            title=target_record.get("title", "Hiring Manager"),
            company=target_record.get("company", target_company),
            linkedin_url=target_record.get("linkedin_url"),
            email=target_record.get("email"),
            source=target_record.get("source", "db"),
            location=target_record.get("location"),
            headline=target_record.get("headline"),
            status=target_record.get("status", "DISCOVERED"),
        )
    else:
        target = build_target(target_name, target_company)

    sent_today = db.count_sent_today()
    if sent_today >= settings.daily_limit:
        return {
            "status": "daily_limit_exceeded",
            "sent_today": sent_today,
            "daily_limit": settings.daily_limit,
        }

    result = orchestrator.run(candidate, target)

    if result.get("eligible"):
        outreach_id = f"outreach-{target.name.lower().replace(' ', '-')}-{datetime.now(timezone.utc).timestamp()}"
        draft = result.get("draft", {})

        db.save_outreach({
            "id": outreach_id,
            "target_id": target.target_id or target.name.lower(),
            "channel": "email",
            "subject": draft.get("subject", f"Intro from {candidate.name}"),
            "message": draft.get("message", ""),
            "match_score": result.get("score", 0),
            "status": "PENDING_APPROVAL",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        approval_token = result.get("approval_token")
        if approval_token:
            db.create_approval_token(outreach_id)

        return {
            "status": "outreach_ready",
            "outreach_id": outreach_id,
            "persistent": True,
            "sent_today": sent_today,
            "daily_limit": settings.daily_limit,
            "result": result,
        }

    return {"status": "outreach_ineligible", "result": result}


def cmd_status() -> dict:
    db = Database()
    settings = get_settings()
    
    with db._connect() as conn:
        all_outreach = conn.execute("SELECT status FROM outreach").fetchall()
        status_counts = {}
        for row in all_outreach:
            status = row["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
    
    sent_today = db.count_sent_today()
    
    return {
        "status": "ok",
        "targets_discovered": status_counts.get("PENDING_APPROVAL", 0) + status_counts.get("APPROVED", 0) + status_counts.get("SENT", 0) + status_counts.get("REJECTED", 0),
        "pending_approval": status_counts.get("PENDING_APPROVAL", 0),
        "approved": status_counts.get("APPROVED", 0),
        "sent": status_counts.get("SENT", 0),
        "rejected": status_counts.get("REJECTED", 0),
        "sent_today": sent_today,
        "daily_limit": settings.daily_limit,
        "can_send": sent_today < settings.daily_limit,
    }


def cmd_report() -> dict:
    db = Database()
    with db._connect() as conn:
        outreach_rows = conn.execute("SELECT status FROM outreach").fetchall()
    status_counts = {}
    for row in outreach_rows:
        status = row["status"]
        status_counts[status] = status_counts.get(status, 0) + 1

    summary = {
        "jobs_discovered": len(db.list_jobs()),
        "pending_approval": status_counts.get("PENDING_APPROVAL", 0),
        "approved": status_counts.get("APPROVED", 0),
        "sent": status_counts.get("SENT", 0),
    }
    generator = ReportGenerator()
    path = generator.build(summary)
    return {"status": "report_generated", "path": path, "summary": summary}


def cmd_dashboard() -> dict:
    return cmd_report()


def cmd_daemon_start() -> dict:
    """Start the background daemon."""
    daemon = ReachAIDaemon()
    if daemon.is_running():
        pid = daemon.read_pid()
        return {"status": "already_running", "pid": pid}
    
    # Start daemon (would run in background in production)
    print("Starting ReachAI daemon... (running in foreground for demo)")
    print("Press Ctrl+C to stop")
    daemon.start()
    return {"status": "stopped"}


def cmd_daemon_stop() -> dict:
    """Stop the background daemon."""
    daemon = ReachAIDaemon()
    return daemon.stop()


def cmd_daemon_status() -> dict:
    """Get daemon status."""
    daemon = ReachAIDaemon()
    return daemon.status()


def cmd_ingest_targets(csv_path: str) -> dict:
    """Ingest targets from CSV file."""
    ingestion = CSVIngestionSkill()
    return ingestion.ingest_targets(csv_path)


def cmd_ingest_jobs(csv_path: str) -> dict:
    """Ingest jobs from CSV file."""
    ingestion = CSVIngestionSkill()
    return ingestion.ingest_jobs(csv_path)


def cmd_list_targets(status: str | None = None) -> dict:
    """List all targets."""
    ingestion = CSVIngestionSkill()
    targets = ingestion.list_targets(status=status)
    return {
        "status": "ok",
        "count": len(targets),
        "targets": targets,
    }


def cmd_list_jobs() -> dict:
    """List all jobs."""
    ingestion = CSVIngestionSkill()
    jobs = ingestion.list_jobs()
    return {
        "status": "ok",
        "count": len(jobs),
        "jobs": jobs,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="ReachAI local CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("setup")
    subparsers.add_parser("discover")
    subparsers.add_parser("rank")
    subparsers.add_parser("outreach")
    subparsers.add_parser("status")
    subparsers.add_parser("report")
    subparsers.add_parser("dashboard", help="Generate the ReachAI dashboard")
    subparsers.add_parser("daemon-start", help="Start background approval/send daemon")
    subparsers.add_parser("daemon-stop", help="Stop background daemon")
    subparsers.add_parser("daemon-status", help="Check daemon status")
    
    # Ingestion commands
    ingest_targets_parser = subparsers.add_parser("ingest-targets", help="Import targets from CSV")
    ingest_targets_parser.add_argument("csv_path", help="Path to CSV file")
    
    ingest_jobs_parser = subparsers.add_parser("ingest-jobs", help="Import jobs from CSV")
    ingest_jobs_parser.add_argument("csv_path", help="Path to CSV file")
    
    subparsers.add_parser("list-targets", help="List all targets")
    subparsers.add_parser("list-jobs", help="List all jobs")
    
    args = parser.parse_args()

    if args.command == "setup":
        print(json.dumps(cmd_setup(), indent=2))
    elif args.command == "discover":
        print(json.dumps(cmd_discover(), indent=2))
    elif args.command == "rank":
        print(json.dumps(cmd_rank(), indent=2))
    elif args.command == "outreach":
        print(json.dumps(cmd_outreach(), indent=2))
    elif args.command == "status":
        print(json.dumps(cmd_status(), indent=2))
    elif args.command == "report":
        print(json.dumps(cmd_report(), indent=2))
    elif args.command == "dashboard":
        print(json.dumps(cmd_dashboard(), indent=2))
    elif args.command == "daemon-start":
        cmd_daemon_start()
    elif args.command == "daemon-stop":
        print(json.dumps(cmd_daemon_stop(), indent=2))
    elif args.command == "daemon-status":
        print(json.dumps(cmd_daemon_status(), indent=2))
    elif args.command == "ingest-targets":
        print(json.dumps(cmd_ingest_targets(args.csv_path), indent=2))
    elif args.command == "ingest-jobs":
        print(json.dumps(cmd_ingest_jobs(args.csv_path), indent=2))
    elif args.command == "list-targets":
        print(json.dumps(cmd_list_targets(), indent=2))
    elif args.command == "list-jobs":
        print(json.dumps(cmd_list_jobs(), indent=2))


if __name__ == "__main__":
    main()
