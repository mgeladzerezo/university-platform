import time
from typing import Protocol

from fastapi import Request

from app.errors import TooManyRequests


class RateLimiter(Protocol):
    def allow(self, key: str, limit: int, window_seconds: int) -> bool: ...


class RedisRateLimiter:
    """Fixed-window counter: one Redis key per client per window."""

    def __init__(self, redis_client):
        self._redis = redis_client

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        window = int(time.time()) // window_seconds
        redis_key = f"ratelimit:{key}:{window}"
        pipe = self._redis.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, window_seconds)
        count, _ = pipe.execute()
        return count <= limit


def client_ip(request: Request) -> str:
    # uvicorn runs with --proxy-headers behind the ingress, so client.host is
    # already the forwarded address.
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request, scope: str, limit: int, window_seconds: int) -> None:
    limiter: RateLimiter = request.app.state.services.rate_limiter
    if not limiter.allow(f"{scope}:{client_ip(request)}", limit, window_seconds):
        raise TooManyRequests("Rate limit exceeded, try again later")
