import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    APP_NAME: str = "Dynalunch API"
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

    # Database (local SQLite by default)
    DATABASE_URL: str = "sqlite:///./dynalunch.db"

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
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# --- GOOGLE CLOUD CREDENTIALS SETUP --- 
creds_path = settings.GOOGLE_APPLICATION_CREDENTIALS
print(f"[DEBUG] GOOGLE_APPLICATION_CREDENTIALS from settings: {creds_path}")
if creds_path:
    # Convert to absolute path if relative (for Windows local development)
    if not os.path.isabs(creds_path):
        # Get current working directory (should be backend/ when running uvicorn)
        cwd = os.getcwd()
        print(f"[DEBUG] Current working directory: {cwd}")
        creds_path = os.path.abspath(os.path.join(cwd, creds_path))
        print(f"[DEBUG] Converted relative path to absolute: {creds_path}")
    
    file_exists = os.path.exists(creds_path)
    print(f"[DEBUG] Credentials file exists at {creds_path}: {file_exists}")
    
    if file_exists:
        # Set the environment variable for Google Cloud libraries
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
        print(f"[DEBUG] Set OS environment variable GOOGLE_APPLICATION_CREDENTIALS")
    else:
        print(f"[WARNING] Credentials file not found at {creds_path}")
else:
    print("[DEBUG] GOOGLE_APPLICATION_CREDENTIALS is not set - agent decision will fail")
# --- END GOOGLE CLOUD CREDENTIALS SETUP ---
