# Exception Learning Readiness Harness

This harness checks whether DAD's exception learning queue stays conservative
when evidence is mixed, weak, below sample threshold, malformed,
private-origin, or backfill-only.

It exists because an exception lake can fail quietly: a single validated fix can
make a cluster look learnable while unresolved siblings, invalid fix rows, or
path-signal backfill evidence are still present. The queue must expose those
blockers instead of creating false promotion confidence.

Run:

```text
python -m digital_asset_directory.cli exceptions learning-check --scenarios assets/coding-harnesses/exception-learning-readiness/examples/synthetic-learning-readiness-scenarios.json
```

The check creates temporary synthetic hubs and repos, writes only safe metadata,
runs the real exception event and fix-outcome APIs, then compares the generated
learning queue against expected statuses and blockers.

The report is generated candidate evidence. It checks only that the supplied
synthetic cases still produce conservative learning-readiness statuses using
the scenario-declared sample threshold. It does
not prove real repo completeness, promote lessons, or authorize source repo
changes.

Current case families:

- clean public validated fixes can enter human lesson review only after the
  comparable-event threshold is met;
- one-off validated fixes remain counts-only until more evidence exists;
- mixed validated and unresolved evidence stays blocked;
- schema-invalid legacy fix rows are quarantined and do not count as fixes;
- unknown or non-public origin evidence requires human release before
  public-facing reuse;
- backfill-only path signals need source review and cannot promote learning;
- human-confirmed backfill review decisions remain labels only until source
  packets or observed exception/fix evidence exist.
