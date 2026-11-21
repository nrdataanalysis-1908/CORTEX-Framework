from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    openai_api_key: str
    api_access_token: str | None = Field(default=None, min_length=32)
    api_rate_limit_requests_per_minute: int = Field(default=60, ge=1, le=100_000)
    embedding_model: str = "text-embedding-3-small"
    chat_model: str = "gpt-4o-mini"
    embedding_dimensions: int = 1536
    chunk_size: int = 1200
    chunk_overlap: int = 200
    top_k: int = 5
    openai_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    openai_max_retries: int = Field(default=2, ge=0, le=5)
    openai_retry_base_delay_seconds: float = Field(default=0.5, gt=0, le=30)
    openai_retry_max_delay_seconds: float = Field(default=8.0, gt=0, le=120)
    circuit_breaker_failure_threshold: int = Field(default=5, ge=1, le=100)
    circuit_breaker_recovery_timeout_seconds: float = Field(default=30.0, gt=0, le=3600)
    embedding_max_concurrency: int = Field(default=4, ge=1, le=100)
    chat_max_concurrency: int = Field(default=4, ge=1, le=100)
    database_connect_timeout_seconds: int = Field(default=5, ge=1, le=60)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
