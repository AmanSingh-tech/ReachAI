from dataclasses import dataclass


@dataclass(frozen=True)
class OutreachPolicy:
    daily_limit: int = 5
    minimum_score: int = 75
    max_message_length: int = 400
    max_llm_retries: int = 2
    require_human_approval: bool = True
    allowed_roles: tuple[str, ...] = (
        "recruiter",
        "technical recruiter",
        "talent acquisition",
        "hiring manager",
        "engineering manager",
        "head of engineering",
        "founder",
    )


POLICY = OutreachPolicy()
