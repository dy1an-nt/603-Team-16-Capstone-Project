from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings loaded from environment variables or the repo-root .env file."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_fallback_model: str = "openai/gpt-oss-20b"

    database_url: str = "postgresql://resume:resume@localhost:5432/resume_reviewer"

    secret_key: str = "dev-only-change-me"
    access_token_expire_minutes: int = 60

    frontend_origin: str = "http://localhost:5500"
    max_upload_mb: int = 5
    libreoffice_path: str = "soffice"


@lru_cache
def get_settings() -> Settings:
    return Settings()
