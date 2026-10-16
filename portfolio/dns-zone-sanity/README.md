# DNS Zone Sanity

Lint normalized DNS exports for CNAME collisions, malformed IP records and SPF policy mistakes without sending queries.

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

Normalized export format only. SPF lookup count is a lower bound without recursive resolution. No DNS queries, DKIM validation, DNSSEC verification or full zone grammar.

Only analyze files and exports you are authorized to use. All bundled evidence is synthetic. No credential use, paid APIs, exploit execution or remote scanning. Source text and JSON are treated as data, never executed. Large or hostile inputs need an external resource limit.

## Next increment

Parse zone files, handle split TXT strings and add fixture-based SPF recursion with explicit query budgets.

See `STATUS.md` for current verification and `SECURITY.md` for reporting guidance. CI runs the same behavioral tests on Linux and Windows, Python 3.11 and 3.13.
