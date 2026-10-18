import os
from dataclasses import dataclass

from dotenv import load_dotenv


# Keep local development configuration in one place. Existing shell variables win
# over values in .env, which is important for tests and production overrides.
load_dotenv(override=False)


@dataclass
class Settings:
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "openai/gpt-4o-mini"
    app_env: str = "development"
    daily_limit: int = 5
    min_score: int = 75
    max_retries: int = 2
    gmail_credentials_path: str = ""
    gmail_token_path: str = ""
    gmail_scopes: str = (
        "https://www.googleapis.com/auth/gmail.send "
        "https://www.googleapis.com/auth/gmail.modify"
    )
    db_path: str = "data/reachai.db"
    candidate_path: str = "data/candidate.json"
    send_mode: str = "dry-run"
    host: str = "127.0.0.1"
    port: int = 8000
    apollo_api_key: str = ""
    public_url: str = ""
    enrich_per_run: int = 10


def get_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", os.getenv("OPENROUTER_API_KEY", "")),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        llm_model=os.getenv("LLM_MODEL", "openai/gpt-4o-mini"),
        app_env=os.getenv("APP_ENV", "development"),
        daily_limit=int(os.getenv("REACHAI_DAILY_LIMIT", "5")),
        min_score=int(os.getenv("REACHAI_MIN_SCORE", "75")),
        max_retries=int(os.getenv("REACHAI_MAX_RETRIES", "2")),
        gmail_credentials_path=os.getenv("GMAIL_CREDENTIALS_PATH", ""),
        gmail_token_path=os.getenv("GMAIL_TOKEN_PATH", ""),
        gmail_scopes=os.getenv(
            "GMAIL_SCOPES",
            "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.modify",
        ),
        db_path=os.getenv("REACHAI_DB_PATH", "data/reachai.db"),
        candidate_path=os.getenv("REACHAI_CANDIDATE_PATH", "data/candidate.json"),
        send_mode=os.getenv("REACHAI_SEND_MODE", "dry-run").strip().lower(),
        host=os.getenv("REACHAI_HOST", "127.0.0.1"),
        port=int(os.getenv("REACHAI_PORT", "8000")),
        apollo_api_key=os.getenv("APOLLO_API_KEY", ""),
        public_url=os.getenv("REACHAI_PUBLIC_URL", ""),
        enrich_per_run=int(os.getenv("REACHAI_ENRICH_PER_RUN", "10")),
    )
