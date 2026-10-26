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
