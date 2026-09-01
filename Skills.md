# ReachAI Skills

This project uses a skill-based workflow to keep outreach reasoning modular, auditable, and safe. The active source-of-truth is the per-skill documentation under `.claude/skills`, while the `.agents/skills` folders are compatibility placeholders and should not be treated as the real implementation.

## Core workflow

1. Candidate profile
2. Target discovery
3. Eligibility filtering
4. Job/target scoring
5. Research and evidence gathering
6. Personalization
7. Critic review
8. Human approval gate
9. Sending only approved outreach
10. Audit logging and reporting

## Skills

### Candidate Profile
Build a canonical user profile from resume, experience, strengths, and target roles. Keep the data structured and grounded in the user's actual background.

### Target Discovery
Ingest targets from CSV or data sources, normalize the fields, deduplicate by identity, and produce a clean target list with source metadata.

### Eligibility
Reject blocks, duplicates, and clearly out-of-scope targets before drafting. Only proceed with targets that are legitimate and relevant.

### Scoring
Score the fit between the candidate and each job or target using role relevance, skills overlap, company fit, and evidence quality.

### Research
Collect factual context about the company, target, and hiring signal. Do not invent claims or overstate confidence.

### Personalization
Create concise, evidence-based outreach that references real signals and ties the candidate to the role or company.

### Critic
Review the message for unsupported claims, generic language, and weak fit. Reject drafts that are not credible or precise.

### Approval
Require explicit human approval before sending. Validate signed approval tokens, update the record state, and refuse invalid or replayed approvals.

### Send
Send only approved outreach using the Gmail API or another supported channel. Record delivery state and preserve audit history.

## Hard rules

- Never fabricate candidate experience
- Never fabricate target facts
- Never contact blocked or previously contacted targets
- Never exceed the daily outreach limit
- Never send directly from the model
- All outbound actions must pass through the approval gate and proper send layer
- Preserve audit history in the local database
