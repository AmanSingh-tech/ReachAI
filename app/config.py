import os
from dataclasses import dataclass


@dataclass
class Settings:
    openai_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    app_env: str = "development"


def get_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        app_env=os.getenv("APP_ENV", "development"),
    )
