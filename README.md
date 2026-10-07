# Kalinowo University platform

Web platform for **Uniwersytet Kalinowski (Kalinowo University)**: public site,
content management, admissions, a student and lecturer portal, and an AI
assistant that answers from published content.

The university is fictional. This repository is a case study; names, addresses
and data are invented.

## What it does

| Area | Features |
|------|----------|
| Public site (PL/EN) | Home, faculties, searchable programme catalogue, news, events, staff directory, contact form |
| Content management | Pages, news and events with a draft -> review -> publish workflow; publishing needs a second editor |
| Admissions | Multi-step application, document upload to S3 with virus scanning, status tracking, staff review queue, decision e-mails |
| Student portal | Course enrollment with capacity limits and waitlists, timetable, grades, announcements |
| Lecturer portal | Rosters, grade entry, course announcements |
| AI assistant | Public chat over published content (retrieval, SSE streaming, source links, refusal when not covered); staff-only application summary with a missing-document checklist |

Roles: `applicant`, `student`, `lecturer`, `editor`, `admissions_officer`, `admin`.

## Architecture

```
browser ── CloudFront + WAF ── ALB ingress ─┬─ web  (Next.js, App Router)
                                            └─ api  (FastAPI) ──┬─ PostgreSQL (RDS, pgvector)
                                                    │           ├─ Redis (ElastiCache)
Keycloak (OIDC) ── JWT ─────────────────────────────┘           ├─ S3 (documents, presigned URLs)
                                                                └─ Anthropic API
                                 worker (Celery) ── e-mail (SES), ClamAV scan, embedding jobs
                                 beat   (Celery) ── nightly retention job
```

- **backend/** One FastAPI application split into modules: `content`,
  `admissions`, `academics`, `notifications`, `assistant`. Each has `models`,
  `schemas`, `service` (rules), `router` (HTTP) and, where needed, `jobs`.
  SQLAlchemy 2 (sync sessions), Alembic, Pydantic v2.
- **frontend/** Next.js with next-intl (PL/EN), Tailwind, TanStack Query and a
  TipTap editor. Public pages are server-rendered; portal pages are client
  components that call the API with the Keycloak access token. API types are
  generated from the backend's OpenAPI schema (`npm run gen:api`).
- **deploy/terraform/** VPC, EKS, RDS PostgreSQL Multi-AZ, ElastiCache, S3,
  CloudFront + WAF, ECR, SES, Secrets Manager, IAM via EKS Pod Identity.
- **deploy/helm/university/** web, api, worker and beat Deployments, HPA,
  PodDisruptionBudgets, NetworkPolicies, ExternalSecret, migration Job as a
  pre-sync hook.
- **deploy/k6/** load script for the enrollment rush. **docs/runbook.md** operations notes.

Everything that talks to the outside world sits behind a small interface and is
collected in one `Services` object (`backend/app/services.py`): token verifier,
object storage, e-mail sender, virus scanner, job queue, rate limiter, embedder,
chunk store, LLM client. Production wires the real implementations; tests wire fakes.

## Run locally

Requires Docker.

```
docker compose up --build
docker compose exec api python -m app.seed      # demo faculties, courses, published pages
```

| URL | What |
|-----|------|
| http://localhost:3000 | Site |
| http://localhost:8000/docs | API (OpenAPI UI) |
| http://localhost:8080 | Keycloak (admin / admin) |
| http://localhost:8025 | Mailpit (outgoing e-mail) |
| http://localhost:9001 | MinIO console (minioadmin / minioadmin) |

Development users (password `password`): `applicant`, `student`, `lecturer`,
`editor`, `reviewer` (second editor), `officer`, `admin`.

The assistant needs `ANTHROPIC_API_KEY` in the environment of `docker compose`.
Without it the chat reports that it is unavailable; everything else works. The
compose stack uses the hashing embedder so no model has to be downloaded.

Without Docker, the API also starts against SQLite for a quick look at the
public site (no Redis, so the chat and contact form will fail):

```
cd backend
py -3.12 -m venv .venv ; .venv\Scripts\pip install -e ".[dev]"
$env:UNI_DATABASE_URL='sqlite:///dev.db'; $env:UNI_EMBEDDER='hashing'; $env:UNI_VECTOR_STORE='json'
.venv\Scripts\alembic upgrade head ; .venv\Scripts\python -m app.seed
.venv\Scripts\uvicorn app.main:create_production_app --factory --port 8000
```

## Test

```
cd backend
pytest                          # SQLite + in-memory fakes, no services needed
ruff check . ; ruff format --check .
python -m app.assistant.evaluation.runner     # retrieval evaluation, fake embedder

cd frontend
npm run lint ; npm run typecheck ; npm test ; npm run build
```

To run the backend suite against PostgreSQL (schema built by the Alembic
migrations, real row locks):

```
$env:TEST_DATABASE_URL='postgresql+psycopg://uni:uni@localhost:5432/uni_test'
pytest
```

`TEST_MIGRATION_TARGET=0002` stops before the pgvector migration on a server
without that extension. CI runs both variants; see `.github/workflows/ci.yml`.

What the tests cover, by the four areas that have to be right:

1. **Enrollment** (`tests/test_enrollment.py`): capacity, waitlist order,
   promotion on drop and on capacity increase, and four concurrency tests
   (40 simultaneous enrollments for 5 seats, concurrent HTTP requests, the same
   student twice at once, mixed drops and enrollments).
2. **Roles** (`tests/test_route_roles.py`): generated from the route table.
   Every route must be on an explicit public allow-list or declare
   `require_roles`; each protected route is called without a token (401), with
   every role that is not allowed (403) and with every allowed role.
3. **Content workflow** (`tests/test_content_workflow.py`): every legal and
   illegal transition, four-eyes publishing, only published content public,
   indexing only after publication, chunks removed on unpublish.
4. **Documents** (`tests/test_admissions.py`): access log entries for upload,
   view and download; retention deletes only rejected applications older than
   the configured period, including their files, and keeps the audit trail.

## Decisions and trade-offs

**Enrollment.** A seat is taken with one statement,
`UPDATE course_offerings SET enrolled_count = enrolled_count + 1 WHERE id = ? AND enrolled_count < capacity`,
and a `CHECK` constraint backs it up. On top of that, every operation that
changes seats or the waitlist of an offering first locks that offering's row
(`SELECT ... FOR NO KEY UPDATE`). The conditional update alone prevents
oversubscription; the lock is what keeps the waitlist consistent (nobody waits
while a seat is free, promotions happen in order). The price is that enrollments
for one course are serialised. Requests for different courses do not block each
other, and a per-course queue is what "first come, first served" means anyway.

An earlier version tried to skip the lock on the fast path. Running the tests
against PostgreSQL showed a deadlock: inserting an enrollment takes a
`FOR KEY SHARE` lock on the offering through the foreign key, and two
transactions then both asked for `FOR UPDATE`. SQLite cannot show this because
it has one writer at a time, which is why CI runs the suite on PostgreSQL too.

**SQLite in tests.** The default test run needs no services, which keeps it
fast and runnable anywhere. SQLite serialises writers, so there the concurrency
tests check the logic and thread-safety but not row-level locking; the
PostgreSQL run does. With the lock and the conditional update replaced by a
naive read-then-write, three of the four concurrency tests fail on PostgreSQL.

**Auth.** The API never sees passwords. It validates Keycloak RS256 access
tokens (signature via JWKS, issuer, audience, expiry) and reads realm roles.
`require_roles(...)` is a dependency on each route; `admin` passes every check.
Object-level rules sit in the services: applicants only load their own
applications (a foreign id is a 404, not a 403), lecturers only touch their own offerings.

**Content workflow.** Only drafts are editable, so what a reviewer approved is
exactly what gets published. Changing published content means unpublish, edit,
review, publish. Simple to reason about, at the cost of the page being offline
during the edit. Body HTML is sanitised on save with an allow-list (nh3).

**Documents.** Browsers upload straight to S3 with a presigned POST, which lets
S3 enforce the size limit; the API re-checks the size when the upload is
completed. Files become downloadable only after the ClamAV job marks them
clean. Object keys never contain the user's file name. Every upload, staff
view, download and AI summary is written to `document_access_log`, which has no
foreign keys on purpose so that it survives the retention job.

**E-mail.** Outbox pattern: the e-mail row is written in the same transaction
as the decision, the Celery job is enqueued after commit. A crash in between
leaves a `queued` row that can be re-sent, never a decision without a record.

**Search.** PostgreSQL full-text search on generated `tsvector` columns with
GIN indexes; a `LIKE` fallback for SQLite. The `simple` text search
configuration is used because PostgreSQL ships no Polish dictionary, so there
is no stemming: "stypendium" does not match "stypendia".

**Assistant.**
- Only chunks of *published* content items are indexed, and the search query
  filters on `status = 'published'` again, so a stale chunk cannot leak a draft.
  Unpublishing deletes chunks in the same transaction as the status change.
- The staff directory, applications and student data are never indexed. The
  chat endpoint takes no credentials, so no user identity reaches the model.
  E-mail addresses and long digit sequences typed by a visitor are redacted
  before the question is embedded or sent.
- Refusal has two gates: if no chunk reaches the similarity threshold the
  model is not called at all; otherwise the system prompt tells the model to
  answer `NO_ANSWER` when the sources do not cover the question, and the API
  turns that sentinel into the refusal message.
- Prompt injection: a small pattern filter rejects the obvious attempts, source
  text and the question are HTML-escaped inside tags so they cannot close them,
  and the model has no tools and no private data, so a successful injection has
  nothing to reach. The UI renders answers as plain text. The tests cover the
  filter and the prompt structure; they cannot prove how the real model behaves.
- Embeddings: `E5Embedder` (multilingual-e5-small, 384 dimensions, optional
  `embeddings` extra) with pgvector in production; a deterministic
  `HashingEmbedder` with cosine search in Python for tests and local runs.
- Model: `claude-opus-5-5` through the Anthropic Python SDK, configurable with
  `UNI_ANTHROPIC_MODEL`. The code sends `output_config.effort`, so the
  configured model has to support that parameter.
- Staff summary: the prompt contains education, statement and document list
  but no name, birth date or contact details. The missing-document checklist is
  computed in Python, not by the model. Each call is recorded in `ai_audit_log`
  before the model is called.
- Evaluation: `backend/app/assistant/evaluation/` holds 22 questions with the
  expected source page (or `null` for "must refuse"). With the hashing embedder
  21 of 22 pass; the miss is an unrelated English question ("Who won the
  football world cup in 2018?") that clears the threshold through hash
  collisions and would then rely on the model's `NO_ANSWER` rule.

**Infrastructure.** Plain Terraform resources instead of community modules, so
every resource is visible in the repository. Pods get AWS credentials through
EKS Pod Identity; application secrets live in Secrets Manager and reach the
cluster through External Secrets. One backend image serves as api, worker, beat
and migration job.

## Known limitations

- **Not verified in this repository's development environment:** Docker image
  builds, the docker-compose stack, the GitHub Actions workflow, `terraform
  plan/apply`, the pgvector code path (`PgVectorChunkStore`, migration `0003`),
  the E5 embedder, real calls to the Anthropic API, Keycloak login in the
  browser, SES and ClamAV against real services, and the k6 script. Terraform
  was validated and the Helm chart linted and rendered, nothing was applied.
- `UNI_ASSISTANT_MIN_SCORE` defaults to 0.80 for the E5 model. That value is an
  estimate and has to be calibrated with the evaluation runner (`--embedder e5`).
- Server-side refusal fallbacks of the Anthropic API are not enabled; a model
  refusal is shown to the visitor as "temporarily unavailable".
- The assistant is single-turn: each question is answered without chat history.
- The rate limiter is a fixed window per client IP; a burst across a window
  boundary can reach twice the limit.
- Accepted applicants are not turned into students automatically. Roles are
  assigned in Keycloak.
- One application per applicant and programme; a withdrawn application cannot be reopened.
- The retention job covers rejected applications only, as specified. Withdrawn
  and abandoned drafts are kept.
- Published content cannot be edited in place (see above), and there is no
  version history of content bodies, only of status changes.
- Python dependencies are lower-bounded in `pyproject.toml` without a lock
  file, so builds are not reproducible to the patch version.
- The Celery worker exposes no Prometheus endpoint; job health is visible in
  logs and in the `email_messages` table only.
- Catalogue administration (faculties, programmes, staff, courses) has API
  endpoints for creation but no UI and no update or delete endpoints.
- Accessibility was built in (landmarks, labels, focus styles, `lang`, live
  regions, tables with headers) but not audited with assistive technology.
- On the very first deployment the secret used by the migration hook has to be
  bootstrapped once; see `docs/runbook.md`.
