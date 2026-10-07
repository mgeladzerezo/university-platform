from dataclasses import dataclass

from app.assistant.embeddings import Embedder
from app.assistant.llm import LlmClient
from app.assistant.store import ChunkStore
from app.auth import TokenVerifier
from app.config import Settings
from app.jobs import JobQueue
from app.notifications.senders import EmailSender
from app.ratelimit import RateLimiter
from app.scanning import VirusScanner
from app.storage import ObjectStorage


@dataclass
class Services:
    """Everything that talks to the outside world, behind small interfaces.

    The API and the worker build this once at startup; tests build it from fakes.
    """

    settings: Settings
    token_verifier: TokenVerifier
    storage: ObjectStorage
    email: EmailSender
    scanner: VirusScanner
    jobs: JobQueue
    rate_limiter: RateLimiter
    embedder: Embedder
    chunk_store: ChunkStore
    llm: LlmClient


def build_services(settings: Settings) -> Services:
    import redis

    from app.assistant.embeddings import E5Embedder, HashingEmbedder
    from app.assistant.llm import AnthropicLlm
    from app.assistant.store import JsonChunkStore, PgVectorChunkStore
    from app.auth import jwks_key_resolver
    from app.celery_app import celery_app
    from app.jobs import CeleryJobQueue
    from app.notifications.senders import SesEmailSender, SmtpEmailSender
    from app.ratelimit import RedisRateLimiter
    from app.scanning import ClamAvScanner
    from app.storage import S3Storage

    if settings.email_backend == "ses":
        email = SesEmailSender(settings.s3_region, settings.email_from)
    else:
        email = SmtpEmailSender(settings.smtp_host, settings.smtp_port, settings.email_from)

    return Services(
        settings=settings,
        token_verifier=TokenVerifier(
            settings.oidc_issuer, settings.oidc_audience, jwks_key_resolver(settings.jwks_url)
        ),
        storage=S3Storage(
            settings.s3_bucket,
            settings.s3_region,
            settings.presign_ttl_seconds,
            settings.s3_endpoint_url,
            settings.s3_public_endpoint_url,
        ),
        email=email,
        scanner=ClamAvScanner(settings.clamav_host, settings.clamav_port),
        jobs=CeleryJobQueue(celery_app),
        rate_limiter=RedisRateLimiter(redis.Redis.from_url(settings.redis_url)),
        embedder=E5Embedder() if settings.embedder == "e5" else HashingEmbedder(),
        chunk_store=PgVectorChunkStore()
        if settings.vector_store == "pgvector"
        else JsonChunkStore(),
        llm=AnthropicLlm(settings.anthropic_model),
    )
