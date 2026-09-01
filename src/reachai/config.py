from dataclasses import dataclass
import os


@dataclass
class Settings:
    openai_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "openrouter/meta-llama/llama-2-70b-chat"
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


def get_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", os.getenv("OPENROUTER_API_KEY", "")),
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        llm_model=os.getenv("LLM_MODEL", "openrouter/meta-llama/llama-2-70b-chat"),
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
    )
