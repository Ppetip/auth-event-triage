# UI Action Contracts

Verify named buttons, form fields and expected state changes against a disposable local HTML fixture. Explicit assertions catch controls that exist but do not work; a missing button fails the contract and stops subsequent actions.

## Run

Python 3.11+:

```sh
python -m pip install -r requirements.txt
python -m playwright install chromium
python tool.py demo.html contract.json
python -m unittest discover -s tests -v
```

Set `RUN_BROWSER_TESTS=1` to include real Chromium integration tests. CI enables these. Exit codes: 0 pass, 1 failed assertion/action, 2 invalid input or missing dependency. Reports include action names and error types, not typed values or DOM dumps.

## Scope

The runner loads HTML into a fresh isolated browser context, blocks HTTP requests and WebSockets, blocks service workers, rejects downloads, closes popup pages and dismisses dialogs. It never visits live accounts. It supports `click` by exact button name, `fill` by exact label, `check` by checkbox name and `text` assertions by role/name. At most 50 steps, 2 seconds per locator action. Assertions use Playwright's retrying expectations.

This is **not an operating-system sandbox**. Use trusted disposable HTML only; JavaScript in the fixture executes in the browser and can consume resources. Network interception is a guardrail, not a defense against malicious browser exploits or all browser protocols. Do not load customer data or secrets. Browser tests install Chromium and use additional disk space.

The demo covers empty validation, save, visible confirmation and reset. It is an initial useful implementation, not proof that arbitrary applications work.

## Next increments

Add checkbox fixture coverage, failure screenshots with masking, accessibility checks, and a documented opt-in adapter for owned staging applications. Keep arbitrary page instructions out of the action plan.

References: [Playwright BrowserContext](https://playwright.dev/python/docs/api/class-browsercontext), [assertions](https://playwright.dev/python/docs/test-assertions).
