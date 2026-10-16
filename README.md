# Auth Event Triage

Correlate failed logins and subsequent success using event-time sliding windows, producing evidence for a SOC analyst.

[Browse the complete 15-project portfolio](PORTFOLIO.md). Five projects are temporarily staged under `portfolio/` pending GitHub’s repository-creation cooldown.

## Run

Python 3.11 or newer. Standard library only; no credentials or services required.

```sh
python tool.py example.json
python -m unittest discover -s tests -v
```

The CLI reads one JSON document (file or `-` for stdin), writes a JSON array, and returns 0 on successful analysis or 2 on invalid input. Findings do not change the process exit status. `example.json` is a synthetic, reproducible input contract. `analyze(data)` is the reusable Python API; see its source and the behavioral tests for edge cases.

## Why this matters

Built for practical employer review: deterministic logic, structured evidence, explicit failure handling, reproducible examples and automated checks. This first release is a focused working baseline. It is not a production security certification.

## Design and boundaries

Normalized JSON input only. Source/user correlation is a heuristic; NAT, distributed attacks, MFA and identity aliases need analyst context. No live log collection.

Only analyze files and exports you are authorized to use. All bundled evidence is synthetic. No credential use, paid APIs, exploit execution or remote scanning. Source text and JSON are treated as data, never executed. Large or hostile inputs need an external resource limit.

## Next increment

Add password-spray correlation across users, JSONL streaming and labeled false-positive evaluation.

See `STATUS.md` for current verification and `SECURITY.md` for reporting guidance. CI runs the same behavioral tests on Linux and Windows, Python 3.11 and 3.13.
