# Exception Capture Completeness Harness

This harness checks whether DAD's repo-side capture rules would emit the right
candidate mail, exception event, fix outcome, local usage record, or no packet for
synthetic situations.

It exists because the LawFirm-os-intake review issue produced DAD-worthy learning,
but Lowell had to notice it and tell the agent to mail DAD. The target behavior is
deterministic: future repos should know which patterns DAD wants, which packets to
send, and when a pattern update means the repo capture surface is stale.

The first layer is synthetic rule coverage. A stronger layer compares expected
emissions to observed JSONL outboxes:

```text
.digital-asset/mail/outbox.jsonl
.digital-asset/exceptions/outbox.jsonl
processed/exceptions/fix-outcomes/outcomes.jsonl
```

The canonical scenario set includes one observed LawFirm-style fixture. Unit tests
also generate a temp repo's mail and exception outboxes through DAD helpers before
evaluating them.

Each positive scenario pins `expected.required_fields` from the matching capture
rule. That means a pattern update must prove both the packet shape and the
metadata fields a repo should emit. Observed outbox checks intentionally fail when
the right mail or exception type exists but the required fields are missing.
Named invariant: `required_fields_pattern_update_contract`. A required field must
be usable and present on one matching packet row; fields split across unrelated or
partial rows do not satisfy capture completeness.

The Mock Trial / Albert `dad_cli_unavailable` case is included as a mail-pattern
scenario. If an enrolled repo cannot run `asset-dir`, it should try the DAD source
checkout entrypoint and then fall back to metadata-only JSONL mail instead of
leaving the issue trapped in chat.

Run:

```text
python -m digital_asset_directory.cli exceptions capture-check --scenarios assets/coding-harnesses/exception-capture-completeness/examples/synthetic-capture-scenarios.json
python -m digital_asset_directory.cli exceptions taxonomy-coverage --fail-on-unrouted --fail-on-missing-scenarios
python -m digital_asset_directory.cli exceptions capture-audit --repo all
python -m digital_asset_directory.cli exceptions capture-audit --repo all --candidate-limit 0
```

The report is candidate evidence. It shows only that the supplied scenarios match
the reviewed capture-rule registry and any observed fixture paths supplied by the
scenario. The observed audit adds a read-only check over repo outboxes and
path signals so DAD can find likely missed emissions in real repos. It compares
candidate pattern families against observed message types, event types, and
capture contracts, so unrelated old mail does not satisfy a missing workflow or
exception capture. Private and unknown repo path signals are hash-only by default.
Each candidate path signal also carries a nested `capture_suggestion` compiled
from the reviewed capture-pattern registry. That nested block gives the exact
candidate packet classes, event types, capture contracts, and required fields a
repo-side agent should consider emitting, while remaining path-signal evidence
only. It is a packet plan, not proof that the path contains a real exception.
Truncated candidate-path scans and strict-only mismatches such as
`type_present_uncorrelated` are review gaps, not clean runs. No single report is
proof that all real repos are complete.
Use `--candidate-limit 0` when the review needs exhaustive metadata-only
path-signal coverage for the selected repo scope; it does not authorize reading
file contents, mutating repos, or promoting backfill candidates. Keep
`--max-scanned-files` explicit for broad scopes; if that ceiling is reached, the
audit remains a truncated review gap until rerun or bounded by a reviewed scope.

The capture, taxonomy, and observed-audit reports emit
`phase6_machine_gate_evidence`. Capture and taxonomy rows support the LawFirm
missed-capture regression, pattern-update simulation, all pattern-family
coverage, sensitive-payload negative tests, and taxonomy route coverage. The
observed-audit report separately supports observed repo capture-audit coverage.
They are machine evidence only: every row uses
`evidence_scope: machine_only_not_roadmap_gate_evidence`, points to
`supports_human_gate_id`, and keeps `human_gate_satisfied` false until a
reviewed roadmap gate is explicitly approved.
The observed-audit evidence fails closed when strict gaps remain, including
unknown capture surfaces, truncated scans, missed-capture candidates,
uncorrelated packet types, or unverified emissions.
A passing observed-audit row only covers the report's declared reviewed scope.
Ad hoc or partial clean scans remain failed for Phase 6 machine evidence, so a
single clean repo cannot masquerade as estate-wide capture coverage.

The taxonomy coverage report checks every reviewed exception event type against
three route classes:

- direct record contracts, meaning a repo agent can intentionally emit safe
  metadata with `asset-dir exceptions record`;
- capture rules with synthetic cases, meaning DAD has an explicit scenario-tested
  detector pattern;
- backfill path-signal rules, meaning DAD can seed candidate historical metadata
  from reviewed path/name terms.

`direct_record_contract_only` is allowed, but it is deliberately visible. It is
not automatic capture coverage.

For outside review, use
`prompts/fable5-exception-capture-and-backfill-red-team.prompt.md`. It asks
Fable 5 to focus on the real failure condition: whether a repo would have emitted
the right DAD packet without Lowell rescuing it from chat, including after DAD
updates capture patterns across asset types.
