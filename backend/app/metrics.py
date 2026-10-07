import time

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_DURATION = Histogram(
    "http_request_duration_seconds", "HTTP request duration", ["method", "route"]
)
ENROLLMENTS = Counter("enrollment_attempts_total", "Enrollment attempts by outcome", ["outcome"])
WAITLIST_PROMOTIONS = Counter("waitlist_promotions_total", "Students promoted from a waitlist")
ASSISTANT_CHATS = Counter(
    "assistant_chat_requests_total", "Public assistant requests by outcome", ["outcome"]
)
RETENTION_PURGED = Counter(
    "admissions_retention_purged_total", "Rejected applications deleted by the retention job"
)


def install_metrics(app: FastAPI) -> None:
    @app.middleware("http")
    async def record_request(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        # Label by route template, not raw path, to keep cardinality bounded.
        # The template is relative to the /api/v1 prefix.
        route = request.scope.get("route")
        template = route.path if route else "unmatched"
        HTTP_REQUESTS.labels(request.method, template, response.status_code).inc()
        HTTP_DURATION.labels(request.method, template).observe(time.perf_counter() - started)
        return response

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
