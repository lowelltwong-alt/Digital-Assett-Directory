# Portfolio Review Operator Trial

Status: implementation evidence complete; supervised live classification pending.
Date: 2026-07-13
Authority: candidate evidence only. This record does not enable a routine,
notification, MCP mutation tool, durable decision writer, or executor.

## Contract under trial

`asset-dir os review` must consume existing strict Portfolio OS cursors without a
Git scan or source rewrite, reuse the cockpit Today list, show categorical
operational health, cap Today at three, and fail closed on missing, stale, invalid,
dirty, unresolved, unscoped, or checker-unknown evidence.

Allowed writes are only the derived `review.html` and `review.json` cursors. The
response template is copy-only and may not record a decision.

## Automated evidence

- strict schema and semantic validation cover source inventory, source hashes,
  stable identities, categorical health, summaries, false-green clearance,
  material fingerprints, and authority fields;
- private labels and absolute paths seeded into source fixtures do not enter JSON
  or HTML;
- missing sources, stale mail, and an applicable dispatch without checker evidence
  never become clear;
- HTML uses CSP and contains no scripts, forms, buttons, or external resources;
- repeated material inputs preserve fingerprints despite a later generation time;
- an injected late JSON failure restores both prior review cursors;
- the compact CLI receipt omits absolute output paths.

Focused result recorded during implementation:

```text
$env:PYTHONPATH='src'
$env:DAD_PYTEST_TMP_ROOT='<workspace>/.tmp/portfolio-review-tests-2'
python -m pytest -q -p no:cacheprovider tests/test_portfolio_review.py
6 passed
```

## Supervised live trial (pending)

Run without enabling a schedule:

```text
asset-dir os refresh --no-scan-portfolio
asset-dir os review
asset-dir os review
```

Capture only categorical results:

- first and second status;
- now/next/waiting/blocked/failed/completed counts;
- health lane states;
- first and second `today_changed`;
- source and ledger zero-write fingerprints;
- whether each displayed row was `useful`, `noisy`, `missing_context`, or `defer`.

Expected: `all_clear=false`, at most three Today rows, stale/unavailable health is
visible, missing checker is `not_applicable` only when no dispatch or validation
requires one, and the second materially identical run reports
`today_changed=false`.

## Kill conditions

Remove the slice if it creates another Today queue, leaks paths or private prose,
hides overflow, reports clear with weak evidence, changes a source cursor, consumes
the JSON change edge on a failed write, or activates any timer, notification,
mutation tool, evaluator, or executor.
