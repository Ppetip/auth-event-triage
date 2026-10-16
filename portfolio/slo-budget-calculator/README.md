# SLO Budget Calculator

Compute request-based error-budget consumption and burn rates for explicitly bounded observation windows.

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

Request-based SLO only. Missing data is not healthy. Does not infer time-to-exhaustion or combine overlapping windows. Floating-point output is approximate.

Only analyze files and exports you are authorized to use. All bundled evidence is synthetic. No credential use, paid APIs, exploit execution or remote scanning. Source text and JSON are treated as data, never executed. Large or hostile inputs need an external resource limit.

## Next increment

Add multi-window burn alerts, explicit telemetry completeness and time-based SLO support.

See `STATUS.md` for current verification and `SECURITY.md` for reporting guidance. CI runs the same behavioral tests on Linux and Windows, Python 3.11 and 3.13.
