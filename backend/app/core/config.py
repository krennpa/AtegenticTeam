import os
from pathlib import Path
from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    APP_NAME: str = "Umamimatch API"
    ENV: str = "local"

    # Security
    SECRET_KEY: str = Field(
        default="dev-secret-change-me",
        description="Secret key for signing JWT tokens",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12  # 12 hours for dev

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Database (local SQLite shared file for hackathon pairing)
    DATABASE_URL: str = "sqlite:///./data/umamimatch.db"

    # LLM provider selection (kept minimal for hackathon prep)
    LLM_PROVIDER: str = Field(default="openai", description="LLM provider: openai | vertexai")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini", description="Default OpenAI chat model")
    VERTEX_MODEL: str = Field(default="gemini-2.5-pro", description="Default Vertex chat model")
    OPENAI_API_KEY: str | None = Field(default=None, description="OpenAI API key")

    # Google Cloud
    GOOGLE_CLOUD_PROJECT: str | None = Field(
        default=None, description="Google Cloud project ID"
    )
    GOOGLE_APPLICATION_CREDENTIALS: str | None = Field(
        default=None, description="Path to Google Cloud service account credentials JSON file"
    )

    # Agent dev fallback (enables a direct LLM ping when agent yields no final response)
    agent_test_fallback: bool = Field(
        default=False, description="Enable agent LLM connectivity fallback during development"
    )

    class Config:
        env_file = str(ROOT_ENV_FILE)
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

def _resolve_google_credentials_path(creds_path: str | None) -> str | None:
    if not creds_path:
        return None
    if os.path.isabs(creds_path):
        return creds_path
    return os.path.abspath(os.path.join(os.getcwd(), creds_path))


def configure_provider_environment() -> None:
    provider = (settings.LLM_PROVIDER or "").strip().lower()
    if provider != "vertexai":
        return

    resolved_path = _resolve_google_credentials_path(settings.GOOGLE_APPLICATION_CREDENTIALS)
    if resolved_path and os.path.exists(resolved_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = resolved_path


configure_provider_environment()
