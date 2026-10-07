# Runbook

Operational notes for the Kalinowo University platform. Commands assume `kubectl`
points at the cluster and the release is `uni` in namespace `university`.

## Components

| Component | Workload | Depends on |
|-----------|----------|------------|
| web | Deployment `uni-web` (Next.js) | api |
| api | Deployment `uni-api` (FastAPI) | PostgreSQL, Redis, Keycloak (JWKS), S3, Anthropic API |
| worker | Deployment `uni-worker` (Celery) | Redis, PostgreSQL, S3, SES, ClamAV |
| beat | Deployment `uni-beat` (Celery beat, 1 replica) | Redis |
| migrate | Job `uni-migrate` (pre-sync hook) | PostgreSQL |

Health endpoints on the api: `/healthz` (process up), `/readyz` (database
reachable), `/metrics` (Prometheus). None of them is exposed through the ingress.

## Deploy

1. CI builds `api` and `web` images tagged with the commit SHA and scans them.
2. Set `image.tag` to that SHA in the environment's values file and sync
   (Argo CD) or run `helm upgrade uni deploy/helm/university -n university -f values-production.yaml --set image.tag=<sha>`.
3. The `uni-migrate` job runs `alembic upgrade head` before pods are replaced.
   If it fails, the rollout does not start; read the job log:
   `kubectl -n university logs job/uni-migrate`.

Because old pods keep serving while the migration runs, every migration has to
work with the previous application version: add columns as nullable or with a
default first, remove them one release later.

### First deployment of an environment

The migration hook needs the `uni-secrets` Secret, which the ExternalSecret in
the same chart creates. On the very first install that Secret does not exist
yet, so bootstrap it once:

```
helm template uni deploy/helm/university -n university -f values-production.yaml \
  --set image.tag=<sha> --show-only templates/config.yaml | kubectl apply -n university -f -
kubectl -n university wait externalsecret/uni-secrets --for=condition=Ready --timeout=120s
```

Then deploy normally. Also required once: set `ANTHROPIC_API_KEY` in the
`<project>-<env>/app` secret in Secrets Manager, publish the SES DKIM records
(`terraform output ses_dkim_tokens`), and point the site's DNS record at
`terraform output cloudfront_domain_name`.

### Rollback

`helm rollback uni <revision> -n university` (or sync the previous commit in
Argo CD). Migrations are not rolled back automatically. Roll the schema back by
hand only when the previous version cannot run against it: start a one-off pod
from the api image with the same `envFrom` as the api Deployment and run
`alembic downgrade -1`.

## Alerts and what to do

### API 5xx rate is high

1. `kubectl -n university logs deploy/uni-api --since=10m | grep -i error`
2. `/readyz` failing means the database is unreachable: check the RDS instance
   status and whether a Multi-AZ failover is in progress (takes 1-2 minutes;
   connections are re-established by `pool_pre_ping`).
3. 401 on every request: the API cannot validate tokens. Check that Keycloak's
   JWKS endpoint is reachable from the pod and that `UNI_OIDC_ISSUER` matches the
   `iss` claim exactly.

### Enrollment is slow during registration opening

Expected shape: every enrollment for one offering takes that offering's row
lock, so requests for the same course queue and p95 latency rises while
throughput stays flat. Requests for different courses do not block each other.

1. Check `enrollment_attempts_total` by outcome and the
   `http_request_duration_seconds` histogram for `/academics/offerings/{offering_id}/enrollment`.
2. Check the HPA: `kubectl -n university get hpa uni-api`. If it is at
   `maxReplicas`, raise `api.autoscaling.maxReplicas`; before a known rush, raise
   `minReplicas` in advance because new nodes take minutes.
3. Check RDS connections: each api pod holds up to 20. `max_connections` of the
   instance class must exceed `pods x 20` plus the workers.
4. Rehearse with `deploy/k6/enrollment-rush.js` against staging before each
   registration period.

Seat counts can be verified at any time; this query must return no rows:

```sql
SELECT o.id, o.capacity, o.enrolled_count, count(e.id) AS enrolled_rows
FROM course_offerings o
LEFT JOIN enrollments e ON e.offering_id = o.id AND e.status = 'enrolled'
GROUP BY o.id
HAVING o.enrolled_count <> count(e.id) OR o.enrolled_count > o.capacity;
```

### Emails are not arriving

Emails are rows in `email_messages` (an outbox) sent by the worker.

1. `SELECT status, count(*) FROM email_messages GROUP BY status;`
   Many `queued`: the worker is not consuming. Many `failed`: read the `error` column.
2. `kubectl -n university logs deploy/uni-worker --since=15m`
3. SES sandbox, suppression list or a missing DKIM record are the usual causes
   of `failed`. Failed sends are retried by Celery up to five times; after that,
   re-enqueue by hand from a worker pod:
   `celery -A app.worker call notifications.send_email --kwargs '{"message_id": 123}'`.

### Uploaded documents stay in "pending_scan"

The scan job could not reach ClamAV or S3.

1. Worker logs, as above. `ConnectionRefusedError` on port 3310 means clamd is
   down or the NetworkPolicy namespace label (`networkPolicy.clamavNamespace`) is wrong.
2. Once fixed, re-enqueue: `celery -A app.worker call admissions.scan_document --kwargs '{"document_id": "<uuid>"}'`.

### Assistant answers "temporarily unavailable"

The api could not get an answer from the Anthropic API.

1. Api logs show the reason: `rate limit reached`, an API status code, or a connection error.
2. 401/403: the key in Secrets Manager is wrong or revoked. Update the secret;
   External Secrets refreshes hourly, or force it with
   `kubectl -n university annotate externalsecret uni-secrets force-sync=$(date +%s) --overwrite`
   and restart the api.
3. 404 on the model: `UNI_ANTHROPIC_MODEL` names a model the key cannot use.

The assistant refusing everything (not an error) means retrieval finds nothing:
check that `content_chunks` has rows (`assistant.index_content` jobs run on
publish) and that `UNI_ASSISTANT_MIN_SCORE` suits the embedding model; re-run
the evaluation set (`python -m app.assistant.evaluation.runner --embedder e5 --min-score 0.8`).

## Routine jobs

- **Retention**: beat enqueues `admissions.purge_rejected` daily at 03:15
  Europe/Warsaw. It deletes rejected applications decided more than
  `UNI_REJECTED_RETENTION_DAYS` ago, files first, then rows, and writes a
  `retention_delete` entry to `document_access_log`. That table is the record
  of what was deleted: the worker has no metrics endpoint, so the
  `admissions_retention_purged_total` counter is not scraped.
- **Beat must run as a single replica.** Two schedulers enqueue every job twice
  (the jobs are idempotent, so this is wasteful rather than harmful).

## Audit questions

- Who opened or downloaded an applicant's documents:
  `SELECT * FROM document_access_log WHERE application_id = '<uuid>' ORDER BY id;`
  or `GET /api/v1/admissions/review/applications/<uuid>/access-log`.
- Which staff used the AI summary: `SELECT * FROM ai_audit_log ORDER BY id DESC;`
  or `GET /api/v1/assistant/audit` (admin).

## Backups and recovery

- RDS: automated backups, 14 days, point-in-time restore. Restore to a new
  instance, update `externalSecret.databaseHost`, sync.
- S3 documents bucket: versioning with 7-day retention of old versions, enough
  to undo an accidental overwrite or delete.
- Redis holds only the Celery queue and rate-limit counters. After losing it,
  queued emails are still in `email_messages` with status `queued` and can be re-enqueued.
