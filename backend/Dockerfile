# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 HF_HOME=/opt/hf
WORKDIR /build
RUN python -m venv /opt/venv && mkdir -p /opt/hf
ENV PATH="/opt/venv/bin:$PATH"
COPY pyproject.toml ./
COPY app ./app
# WITH_EMBEDDINGS=1 adds sentence-transformers (CPU-only torch) and bakes the
# multilingual-e5-small model into the image, so pods need no download at start.
# Production images set it; local development uses the hashing embedder instead.
ARG WITH_EMBEDDINGS=0
RUN if [ "$WITH_EMBEDDINGS" = "1" ]; then \
      pip install --extra-index-url https://download.pytorch.org/whl/cpu ".[embeddings]" \
      && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"; \
    else \
      pip install .; \
    fi

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/opt/venv/bin:$PATH" \
    HF_HOME=/opt/hf HF_HUB_OFFLINE=1
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --no-create-home app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/hf /opt/hf
COPY alembic.ini ./
COPY alembic ./alembic
USER 10001:10001
EXPOSE 8000
# The same image runs the API (default), the Celery worker/beat and migrations;
# Kubernetes and docker-compose override the command.
CMD ["uvicorn", "app.main:create_production_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
