# Sentinel MVP (2026-10-24)

Self-hosted, local-first event ingestion, SQLite persistence, basic detection rules, a reader-authenticated API, and an interactive dashboard with persistent acknowledgment history. **Prototype, not a production SIEM.** The root repo's existing utilities remain unchanged.

## Quick start (Python 3.11+)

```bash
export SENTINEL_INGEST_TOKEN="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
export SENTINEL_READ_TOKEN="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
python -m sentinel.api --db ./sentinel.sqlite3
```

Open http://127.0.0.1:8765/, paste SENTINEL_READ_TOKEN in the reader token field, and connect. Tokens are not saved by the UI. Use a different token for ingesting events. To ingest newline-delimited JSON:

```bash
python -m sentinel.agent events.jsonl
```

Each line must contain exactly id (8–64 ASCII letters/digits/underscore/hyphen), host (ASCII hostname), kind (auth_failure, auth_success, host_down, host_up, integrity_changed), timezone-aware ISO-8601 timestamp within 7 days of now and no more than 5 minutes into the future, and a detail string of at most 512 characters. IDs are idempotent; conflicting reuse is rejected. Payload limit 8192 bytes. Alerts: fifth authentication failure per host within five minutes, host down, and integrity change. Events are not reprocessed retroactively for out-of-order windows.

## Tests

```bash
python -m unittest sentinel.tests.test_sentinel -v
node sentinel/tests/ui_contract.test.cjs
python -m unittest sentinel.tests.test_browser -v  # optional: requires Playwright and Chromium
```

The browser suite launches real local Chromium, tests Connect/Refresh/Filter/Acknowledge, and checks HTML injection is rendered as text. The browser test is skipped if Playwright is missing; browser binary availability or managed browser policies may still fail. CI workflow must actually run before claiming any remote success.

## Docker

Run `docker compose -f sentinel/compose.yaml up --build` after setting both environment variables. Compose publishes only to host loopback; the container uses explicit opt-in to bind to its container interface. Other containers sharing its Docker network can still reach that interface, so **do not attach untrusted containers**. Do not expose directly to the Internet. This prototype has no TLS, credential rotation, per-agent identities, retention or RBAC. The SQLite volume persists events.

## Alert acknowledgment audit history

Successful alert acknowledgments are recorded transactionally in SQLite (`audit_entries`) with timestamp, alert ID, action and `reader_token` role label. Repeated or nonexistent acknowledgments do not add audit entries. The authenticated, bounded `GET /api/audit?limit=50` endpoint and dashboard show this history. This is a shared-token **role audit**, not user attribution or tamper-evident forensic logging. The current model cannot tell which individual used the reader token; real deployments need per-user authentication, RBAC, and protected audit retention.

## Security decisions / limitations

- Two distinct bearer tokens: ingest-only and read/acknowledge; no default credentials, no token persistence in UI.
- Bind to loopback by default; non-loopback allowed only with explicit container opt-in.
- Bounded request body, strict event schema, parameterized SQL, idempotent IDs, and text-only rendering for untrusted event details.
- No HA, queue, TLS termination, RBAC, tamper-evident audit retention, per-user identities, per-agent identities, or production throughput guarantees.
- Before real deployment: HTTPS reverse proxy, per-agent token rotation, per-user audit attribution, rate limits, retention, multi-process concurrency tests and late-event handling.

## Late-event behavior (2026-10-28)

Auth-burst detection now uses event timestamps rather than ingestion order. For each new authentication failure, Sentinel examines that host's failures within five minutes before and after the event, evaluates five-event windows chronologically, and anchors an alert to the latest event in the first qualifying group containing the new arrival. Existing auth-burst alerts within five minutes of that anchor suppress duplicates, including when older events arrive after an alert has fired. Alert acknowledgments and audit history are never retracted.

**Trade-offs:** this is a local ten-minute event-time query per authentication failure, not a streaming watermark or historical backfill engine. Close-by distinct bursts may be deduplicated; high-volume deployments need a first-class incident model, load benchmarks, backpressure and event-time policies.

Browser CI pins Ubuntu 24.04 because Playwright 1.56 cannot install Chromium on Ubuntu 26.04, selected by `ubuntu-latest` during the October 26 run.

## Authenticated ingestion rate limiting (2026-10-30)

The ingestion endpoint uses a thread-safe, process-local token bucket. By default it accepts a
burst of 120 authenticated POST requests and refills at 600 requests per minute. Start the
server with `--ingest-burst 30 --ingest-per-minute 120` to set lower limits. Exhausted
requests return HTTP 429 and a `Retry-After` header; they do not enter the event store.
The reader API remains independent of the ingestion limiter. Limits reset on restart and
are **not shared across multiple processes or hosts**. This is a backpressure safeguard,
not DDoS protection, a distributed quota, or a substitute for a reverse proxy and network
access controls.

The JSONL ingestion client honors `Retry-After` for HTTP 429 and retries each line up to
three times by default (`--max-retries 0..10`), retaining its idempotent event ID. It
returns a nonzero exit code if any line fails, even when earlier lines succeeded. A
persistent rate-limit condition requires slowing the sender or adjusting deployment limits.
