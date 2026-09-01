# ReachAI Plan

## Product goal

Build a personal AI outreach agent for Aman Singh that works with real target lists, qualifies them, personalizes outreach, and requires human approval before sending.

The system should not directly scrape LinkedIn or blindly send messages. Instead, it should:

- ingest approved profile sources
- normalize and deduplicate targets
- score fit based on role and company relevance
- research and personalize outreach
- present each draft for approval
- send only after explicit approval

## Core design change: skill-based architecture

The system should be built as a main orchestrator that calls specialist skills.

This is the right design because it makes the system modular, explainable, and easy to extend.

### Main orchestrator agent

The main agent is responsible for:

- receiving the user request
- selecting the relevant skills
- coordinating the workflow
- making sure the human approval gate is enforced
- checking final quality before sending

### Skills

Each skill handles one specific responsibility.

#### 1. ProfileSkill
Purpose:
- structure and manage the candidate profile
- store your resume-derived strengths, skills, and target roles
- provide a consistent view of your profile to the rest of the system

Example responsibilities:
- load profile
- update skills
- read resume metadata
- return candidate strengths

#### 2. TargetDiscoverySkill
Purpose:
- accept profile sources like CSV imports, URL lists, or approved sources
- normalize and validate target data
- create a list of candidate targets

Example responsibilities:
- ingest targets
- dedupe by URL or name+company
- validate required fields
- create a `TargetProfile` object

#### 3. EligibilitySkill
Purpose:
- decide whether a target is worth contacting
- apply deterministic filters before AI personalization

Example rules:
- recruiter or hiring manager role only
- relevant company/industry match
- not previously contacted
- not blocked or rejected
- target role fits your target list

Output:
- `eligible` or `ineligible`
- reason codes

#### 4. ScoringSkill
Purpose:
- assign a match score from 0 to 100
- quantify how relevant a person is to your profile

Example categories:
- role relevance
- company relevance
- skills overlap
- seniority fit
- domain fit
- hiring signal

Output:
- score
- breakdown

#### 5. ResearchSkill
Purpose:
- gather factual context about the person and company
- identify why the target is relevant

Example outputs:
- company summary
- role summary
- reason for contact
- relevant company details

#### 6. PersonalizationSkill
Purpose:
- write a short, grounded message using your profile and target profile
- personalize based on role, company, and match score

This is where the LLM should be used.

#### 7. CriticSkill
Purpose:
- review generated outreach for quality and safety
- reject or revise weak drafts

Checks:
- personalization exists
- no unsupported claims
- includes resume link
- not generic or spammy
- under length limit

#### 8. ApprovalSkill
Purpose:
- send the draft to the human for approval
- handle approve / reject / edit states
- enforce the final send gate

#### 9. SendSkill
Purpose:
- send only approved messages through a compliant mechanism
- log send status and audit trail

This should remain behind a strict boundary.

## Real data architecture

The system should use real profile data, not hardcoded constants.

### Candidate profile schema

```json
{
  "name": "Aman Kumar Singh",
  "email": "pendulum4441@gmail.com",
  "resume_url": "https://...",
  "skills": ["Python", "LLMs", "RAG", "Agents", "Next.js", "Node.js"],
  "experience": [
    "Google Web Solutions Engineer Intern",
    "AlgoUniversity Software Engineering Co-op Intern",
    "Internloom Web Developer Intern"
  ],
  "strengths": [
    "AI systems",
    "LLM workflows",
    "full-stack product engineering",
    "MLOps"
  ],
  "target_roles": [
    "AI Engineer",
    "Applied AI Engineer",
    "ML Engineer",
    "LLM Engineer"
  ]
}
```

### Target profile schema

```json
{
  "target_id": "local-001",
  "name": "Sarah Chen",
  "role": "Hiring Manager",
  "company": "Northstar Labs",
  "profile_url": "https://linkedin.com/in/...",
  "source": "csv_import",
  "status": "discovered"
}
```

## Recommended high-level workflow

```text
User request
  ↓
Main orchestrator agent
  ↓
ProfileSkill
  ↓
TargetDiscoverySkill
  ↓
EligibilitySkill
  ↓
ScoringSkill
  ↓
ResearchSkill
  ↓
PersonalizationSkill
  ↓
CriticSkill
  ↓
ApprovalSkill
  ↓
SendSkill
```

## Why this is better than a single monolithic agent

This design gives us:

- clear responsibilities
- easier debugging
- easier testing
- better explainability
- better extension for new skills
- a more realistic engineering story

## Real-first implementation path

### Phase 1: profile and target models

- create real candidate profile schema
- create target profile schema
- create route or import flow for CSV/list input
- store target records with local identifiers

### Phase 2: qualification and scoring

- implement eligibility rules
- implement score calculation
- filter out low-fit profiles before writing messages

### Phase 3: research and personalization

- build company/role research skill
- build message personalization skill
- use the real candidate profile and target context

### Phase 4: human approval flow

- show each draft to the user
- allow approve / edit / reject
- keep an audit trail and message preview

### Phase 5: safe sending layer

- only send approved messages
- run through a compliant send mechanism
- log all outcomes

## The best real MVP strategy

For your use case, build this first:

- real candidate profile from your resume
- imported target list from a file or approved source
- skills-based orchestration
- approval-before-send
- no uncontrolled scraping
- no blind automation

That is the right balance between real usage and safe engineering.

## Recommended next step

The next step should be to implement the actual skill layer in code:

1. `ProfileSkill`
2. `TargetDiscoverySkill`
3. `EligibilitySkill`
4. `ScoringSkill`
5. `ResearchSkill`
6. `PersonalizationSkill`
7. `CriticSkill`
8. `ApprovalSkill`
9. `SendSkill`

Then the main orchestrator agent calls them in sequence.

## Review questions

Please answer these:

1. Do you want the first version to take targets from a CSV/import file only, or from a real LinkedIn export later?
2. Should the first approval flow be email-based, in-app, or a simple review UI?
3. Do you want the skill layer implemented as Python classes immediately, or do you want a more lightweight first pass?
4. Should the first version prioritize recruiter outreach, hiring managers, or both?
