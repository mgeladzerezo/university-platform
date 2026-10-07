from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UNI_", env_file=".env", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+psycopg://uni:uni@localhost:5432/uni"
    redis_url: str = "redis://localhost:6379/0"
    public_site_url: str = "http://localhost:3000"
    cors_origins: list[str] = ["http://localhost:3000"]

    oidc_issuer: str = "http://localhost:8080/realms/kalinowo"
    oidc_audience: str = "uni-api"
    # Defaults to the Keycloak certs endpoint under the issuer.
    oidc_jwks_url: str | None = None

    s3_bucket: str = "uni-documents"
    s3_region: str = "eu-central-1"
    # Set for MinIO in local development; leave empty on AWS.
    s3_endpoint_url: str | None = None
    # Host name browsers use for presigned URLs when it differs from the above.
    s3_public_endpoint_url: str | None = None
    presign_ttl_seconds: int = 300
    max_upload_bytes: int = 10 * 1024 * 1024

    email_backend: Literal["ses", "smtp"] = "smtp"
    email_from: str = "no-reply@ukal.example"
    contact_inbox: str = "rektorat@ukal.example"
    smtp_host: str = "localhost"
    smtp_port: int = 1025

    clamav_host: str = "localhost"
    clamav_port: int = 3310

    rejected_retention_days: int = 365

    anthropic_model: str = "claude-opus-5-5"
    embedder: Literal["e5", "hashing"] = "e5"
    vector_store: Literal["pgvector", "json"] = "pgvector"
    assistant_top_k: int = 4
    assistant_min_score: float = 0.80
    chat_rate_limit_per_minute: int = 10
    contact_rate_limit_per_hour: int = 5

    @property
    def jwks_url(self) -> str:
        return self.oidc_jwks_url or f"{self.oidc_issuer}/protocol/openid-connect/certs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
