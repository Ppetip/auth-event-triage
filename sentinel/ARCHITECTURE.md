# Sentinel architecture (work in progress)

Sentinel is a self-hosted security operations platform, consolidating the Auth Event Triage, File Integrity Ledger, and related portfolio utilities into a coherent system.

## Target architecture
Authorized JSONL agents -> bounded authenticated ingestion API -> SQLite event/alert store -> event-time detection rules -> authenticated query API -> local-first dashboard.

The first implemented slice is being tested locally: event validation and deduplication, atomic storage, auth-burst/host-down/integrity detections, API endpoints, a responsive dashboard, and a Playwright interaction suite.

## Security constraints
Loopback-only by default; non-loopback requires TLS reverse proxy, per-agent credentials and access controls before real deployment. Never collect credentials or private logs in portfolio demos. This is not a production SIEM.

## Delivery gates
Unit/API/static UI tests, browser interactions, a container build, CI and documentation must be reviewed before merging. Existing mini-tools are preserved while capabilities migrate.

## Known limitations
Current design does not support RBAC, HA, retention, delivery queues, late-event retractions, agent enrollment or production-scale throughput. These are explicit engineering milestones, not claimed capabilities.
