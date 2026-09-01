# ReachAI Operations Guide

This guide explains how to use the ReachAI local-first outreach assistant.

## Quick Start

### 1. Setup

Initialize the candidate profile:

```bash
python -m reachai.cli setup
```

Output shows your candidate profile and settings.

### 2. Generate Outreach

Create an approval-ready outreach draft:

```bash
python -m reachai.cli outreach
```

Output includes:
- `outreach_id`: Unique ID for this outreach
- `approval_token`: Token for approving via email
- `draft`: The personalized message
- `sent_today`: Count of messages sent today
- `daily_limit`: Maximum outreach per day

**Daily Limit Enforcement**: If you've already sent today's limit, the command will reject new outreach.

### 3. Check Status

View your outreach pipeline:

```bash
python -m reachai.cli status
```

Output:
- `pending_approval`: Drafts awaiting approval
- `approved`: Drafts you've approved
- `sent`: Messages successfully sent
- `rejected`: Drafts you rejected
- `sent_today` / `daily_limit`: Daily send progress
- `can_send`: Whether you can generate more outreach

### 4. Approve Outreach

When you receive an approval email from ReachAI:

1. Read the email (it includes an approval token)
2. Reply with: `APPROVE <token>`
3. The system processes your approval

### 5. Daemon Operations

Run the background approval/send processor:

```bash
# Start daemon (runs in foreground for demo)
python -m reachai.cli daemon-start

# Check daemon status (in another terminal)
python -m reachai.cli daemon-status

# Stop daemon
python -m reachai.cli daemon-stop
```

The daemon:
- Polls Gmail every 60 seconds for approval emails
- Processes approved messages every 5 minutes
- Respects the daily limit
- Tracks all activity in the database

## Database

All data is stored locally in `data/reachai.db`:

- **outreach**: Messages with status (PENDING_APPROVAL, APPROVED, SENT, REJECTED)
- **approval_tokens**: Single-use tokens (7-day expiration)
- **targets**: Contact profiles
- **jobs**: Job postings

Query the database:

```bash
sqlite3 data/reachai.db
sqlite> SELECT * FROM outreach;
sqlite> SELECT status, COUNT(*) FROM outreach GROUP BY status;
```

## Configuration

Set environment variables to customize behavior:

```bash
export OPENAI_API_KEY="sk-..."          # LLM for personalization
export REACHAI_DAILY_LIMIT=5             # Max sends per day (default: 5)
export REACHAI_MIN_SCORE=75              # Minimum match score (default: 75)
export REACHAI_DAILY_LIMIT=5             # Daily outreach limit
```

## Workflow State Diagram

```
┌─────────────────────────────────────────────────┐
│ 1. Generate Outreach (CLI)                      │
│    → Creates PENDING_APPROVAL record            │
│    → Generates approval_token                   │
│    → Sends approval email                       │
└──────────────────────┬──────────────────────────┘
                       │
                       ├─ No Match (ineligible)
                       │  → Workflow ends
                       │
┌──────────────────────┴──────────────────────────┐
│ 2. Receive Approval Email (User's Email)        │
│    → Contains approval_token                    │
│    → User replies: "APPROVE <token>"            │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│ 3. Daemon Polls Gmail (ApprovalLoop)            │
│    → Finds unread "APPROVE" emails              │
│    → Processes approval reply                   │
│    → Updates status → APPROVED                  │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│ 4. Daemon Sends Approved Messages (SendWorker)  │
│    → Finds status=APPROVED records              │
│    → Sends via configured channel               │
│    → Updates status → SENT                      │
│    → Increments sent_today counter              │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│ 5. View Report                                  │
│    → python -m reachai.cli status               │
│    → Shows: pending_approval, sent, rejected    │
└─────────────────────────────────────────────────┘
```

## Rules and Constraints

**Human Approval Gate**
- No message is ever sent without explicit human approval
- Approval tokens are single-use (expire after 7 days)
- Once approved, message is queued for sending

**Daily Limits**
- Default: 5 messages per day
- Counted at send time (not draft time)
- Resets at midnight UTC
- Check with `status` command

**Eligibility Checks**
- Target role must be relevant (hiring manager, recruiter, engineer manager)
- Company should match your interests
- Previous rejections are blocked
- Duplicates are detected

**Blocking**
- Never contact the same person twice
- Blocked targets are tracked in database
- No resume links in generic templates

## Troubleshooting

### "daily_limit_exceeded"

You've sent 5 (or your configured limit) messages today. Check status:

```bash
python -m reachai.cli status
```

Wait until tomorrow or increase `REACHAI_DAILY_LIMIT`.

### "outreach_ineligible"

The target didn't pass eligibility checks. This is a safety feature:

- Role not recognized as hiring/decision-maker
- Company doesn't match your target list
- Target already contacted or blocked

### No approval emails received

Ensure:
1. Gmail is configured (`GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`)
2. Daemon is running
3. Check spam folder for "[ReachAI]" subject

### Database errors

Reset the database (WARNING: deletes all records):

```bash
rm data/reachai.db
```

The system will recreate the schema on next run.

## Complete End-to-End Test

Run the full demonstration workflow:

```bash
python scripts/workflow.py
```

This script shows:
1. Candidate profile setup
2. Outreach generation
3. Simulated approval email
4. Approval processing
5. Message sending
6. Final status

## Next Steps

To integrate with real Gmail:

1. Create OAuth2 credentials at Google Cloud Console
2. Set `GMAIL_CLIENT_ID` and `GMAIL_CLIENT_SECRET`
3. Authorize with your Gmail account
4. Daemon will poll real Gmail for approval replies

To integrate with real outbound providers:

1. Add API keys for Resend, Apollo, Hunter
2. Update [src/reachai/integrations/](src/reachai/integrations/) to use real APIs
3. Daemon will send via real providers

## Architecture

The system is built with:

- **CLI**: Commands for setup, outreach, status, daemon control
- **Orchestrator**: Generates personalized drafts with approval gating
- **Database**: SQLite for persistence and audit trail
- **ApprovalLoop**: Background daemon polling for approval emails
- **SendWorker**: Processes approved messages
- **Skills**: Modular components (eligibility, scoring, personalization, critic, approval)

All components run locally on your laptop—no cloud dependencies in v1.
