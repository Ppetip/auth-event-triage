# Incident Timeline Merge

Normalize timestamped evidence into a UTC timeline, deduplicate stable IDs and detect contradictory records.

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

Normalized JSON only. Timestamps do not prove causality; clocks may skew and evidence may be incomplete. Does not claim forensic chain of custody.

Only analyze files and exports you are authorized to use. All bundled evidence is synthetic. No credential use, paid APIs, exploit execution or remote scanning. Source text and JSON are treated as data, never executed. Large or hostile inputs need an external resource limit.

## Next increment

Add source clock uncertainty, immutable evidence digests and CSV import/export.

See `STATUS.md` for current verification and `SECURITY.md` for reporting guidance. CI runs the same behavioral tests on Linux and Windows, Python 3.11 and 3.13.
