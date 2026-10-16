# Cybersecurity, IT and CS Portfolio

Fifteen independent working baselines, built October 16, 2026. Each repository includes implementation, synthetic examples, behavioral tests, CI and documented limits. These are early releases for incremental development, not production security guarantees.

| Project | Practical purpose |
|---|---|
| [Auth Event Triage](https://github.com/Ppetip/auth-event-triage) | Correlate failed logins and subsequent success using event-time sliding windows, producing evidence for a SOC analyst. |
| [HTTP Header Review](https://github.com/Ppetip/http-header-review) | Review captured HTTP response headers offline and explain actionable browser-hardening gaps. |
| [File Integrity Ledger](https://github.com/Ppetip/file-integrity-ledger) | Create bounded SHA-256 directory manifests and compare snapshots to identify additions, deletions and modifications. |
| [Redacted Secret Audit](https://github.com/Ppetip/redacted-secret-audit) | Find likely credentials in supplied source text while returning only rule, line and irreversible fingerprints. |
| [IAM Policy Lens](https://github.com/Ppetip/iam-policy-lens) | Review AWS-style identity policy JSON for broad allows and explain statement-level evidence. |
| [Firewall Path Explainer](https://github.com/Ppetip/firewall-path-explainer) | Simulate ordered first-match firewall rules for supplied packets and explain redundant or shadowed rules. |
| [SBOM Change Review](https://github.com/Ppetip/sbom-change-review) | Compare CycloneDX-style component inventories, detect ambiguous identities and explain version/license changes. |
| [Certificate Expiry Board](https://github.com/Ppetip/certificate-expiry-board) | Prioritize exported certificate inventories by expiry and not-before dates using an explicit reproducible clock. |
| [Backup Manifest Verify](https://github.com/Ppetip/backup-manifest-verify) | Verify a backup against trusted SHA-256 entries without restoring files, rejecting traversal and symlink paths. |
| [Dependency Runbook](https://github.com/Ppetip/dependency-runbook) | Compute deterministic recovery order and parallelizable stages for service dependencies, rejecting cycles and missing references. |
| [SLO Budget Calculator](https://github.com/Ppetip/auth-event-triage/tree/main/portfolio/slo-budget-calculator) | Compute request-based error-budget consumption and burn rates for explicitly bounded observation windows. |
| [Incident Timeline Merge](https://github.com/Ppetip/auth-event-triage/tree/main/portfolio/incident-timeline-merge) | Normalize timestamped evidence into a UTC timeline, deduplicate stable IDs and detect contradictory records. |
| [Configuration Drift Map](https://github.com/Ppetip/auth-event-triage/tree/main/portfolio/configuration-drift-map) | Compare nested configuration snapshots using JSON Pointer paths with auditable exact-path ignores. |
| [DNS Zone Sanity](https://github.com/Ppetip/auth-event-triage/tree/main/portfolio/dns-zone-sanity) | Lint normalized DNS exports for CNAME collisions, malformed IP records and SPF policy mistakes without sending queries. |
| [UI Action Contracts](https://github.com/Ppetip/auth-event-triage/tree/main/portfolio/ui-action-contracts) | Verify explicit UI contracts on disposable HTML with network blocked. |

## Publication status

Ten independent public repositories were created. GitHub blocked further creation with “You have created too many repositories, too quickly. Please try again later.” The five remaining implementations are published under `portfolio/` in the Auth Event Triage repository with their own tests, examples and CI definitions. A root aggregate workflow runs them there. Their standalone repositories are pending the creation cooldown; the next scheduled review must complete publication before feature work.

## Review cadence

Review every two days over four weeks. Fix CI failures first, then choose one or two substantial improvements using each ROADMAP.md and README. Track evidence in STATUS.md and the coordinator CYCLE_LOG.md. Browser testing runs on disposable HTML with network requests blocked. All examples are synthetic.

Local verification is recorded in verification.json. Remote publication and CI evidence are recorded separately in publication.json. No skipped check counts as a passing executed check.

## Employer review path

Start with Auth Event Triage for SOC correlation, Firewall Path Explainer for deterministic security decisions, Backup Manifest Verify for filesystem safety, Dependency Runbook for graph algorithms, and UI Action Contracts for functional testing. Run the examples and tests, inspect boundary cases, and compare the documented limits with your intended use.

## Licensing

No open-source license has been selected. Public visibility permits review under GitHub terms, but is not a general license grant. The owner can choose a license in a later review.
