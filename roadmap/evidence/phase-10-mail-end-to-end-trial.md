# Phase 10: End-To-End Mail Trial Evidence

Generated: 2026-07-05
Status: machine evidence captured; human gates still pending

## Scope

This evidence covers the Goal 3 end-to-end mail-system trial from
`roadmap/evidence/dad-deployment-and-all-repo-verification-roadmap.md`.

The trial uses synthetic temporary repos only. It does not collect from real
repo outboxes, deliver to real repo inboxes, enroll repos, approve public
release, or mutate source authority.

## Acceptance Mapping

| Requirement | Current evidence | Status |
|---|---|---|
| Repo A outbox mail is collected once. | `tests/test_mail_center.py::test_phase10_two_repo_mail_trial_covers_message_types_digest_and_dedupe` composes five packet families from temp repo A and asserts `collected_count == 5` and `duplicate_count == 0`. | machine-proven, human-review-pending |
| DAD central inbox/outbox/archive records provenance and return address. | The same test asserts central inbox records preserve message types and source return addresses, and delivery logs record delivered plus duplicate-ack events. | machine-proven, human-review-pending |
| Repo B receives candidate mail and digest can read it. | The same test delivers to temp repo B only under reviewed in-test mail policy, asserts five inbox rows, and asserts digest counts five unread messages. | machine-proven, human-review-pending |
| Duplicate delivery does not spam the target inbox. | The same test reruns delivery and asserts `delivered_count == 0`, `acknowledged_duplicate_count == 5`, and repo B receives `inbox_ack` archive rows. | machine-proven, human-review-pending |
| Private/internal/unknown-origin to public-facing target is quarantined until human release. | `tests/test_mail_center.py::test_phase10_agent_triage_does_not_release_unknown_origin_to_public_target` holds unknown-origin mail for public release, proves central agent triage does not release it, then proves explicit human release permits delivery. | machine-proven, human-review-pending |
| CLI operation follows reviewed policy, not just direct function calls. | `tests/test_mail_center.py::test_phase10_cli_reviewed_policy_path_delivers_only_mailbox_files` runs `mail collect --repo all`, `mail route`, and `mail deliver --repo all` through the CLI with reviewed temp policy. | machine-proven, human-review-pending |
| Delivery writes only mailbox files. | The CLI test snapshots temp repo B before and after delivery and asserts every changed path starts with `.digital-asset/mail/`. | machine-proven, human-review-pending |
| Non-public visibility matrix is not only private-origin. | `tests/test_mail_center.py::test_phase10_non_public_visibility_to_public_target_requires_human_release` covers internal and restricted source visibility to public-facing targets. | machine-proven, human-review-pending |
| Concurrent mail storms can distinguish mailbox dirt from worktree dirt. | Synthetic tests prove mailbox dirt is separated from git worktree dirt. Current live DAD storm diagnostics report `spool_dirty=false`, `worktree_dirty=true`, `safe_to_collect=true`, `safe_to_route=true`, and `safe_to_deliver=false`; delivery is held only by reviewed write-protected Logos policy. `rust mail-spool-check` remains alias-only structural evidence and cannot override Python doctor semantics. | machine-proven for distinction, delivery policy hold pending |

## Covered Packet Families

The synthetic two-repo trial covers:

- `lesson_suggestion`
- `asset_suggestion`
- `workflow_suggestion`
- `governance_notice`
- `capability_suggestion` as the exception-adjacent metadata-only packet family

The test intentionally checks message transport, provenance, digest, duplicate
acknowledgement, and mailbox-only write boundaries. It does not claim target
repo adoption or human acceptance.

## Existing Supporting Tests

The broader mail test suite already covers:

- malformed JSONL tolerance and quarantine;
- restricted/confidential sensitivity rejection;
- same-basename target ambiguity;
- reviewed target policy required for explicit delivery paths;
- public-safe payload checks for long evidence, raw/table-like values, and
  local absolute paths;
- source-authored public-release approval spoofing;
- human release rejection;
- digest tolerance of malformed inbox/archive rows;
- dirty-spool wrong-box and duplicate detection.
- Rust leaf mail-spool probing for lock/temp fragments, malformed JSONL,
  oversized rows, Rust rollout packet counts, unsafe aliases, and alias-only
  output.

## Validation

Focused command:

```text
PYTHONPATH=src python -m pytest tests/test_mail_center.py::test_phase10_two_repo_mail_trial_covers_message_types_digest_and_dedupe tests/test_mail_center.py::test_phase10_agent_triage_does_not_release_unknown_origin_to_public_target tests/test_mail_center.py::test_phase10_cli_reviewed_policy_path_delivers_only_mailbox_files tests/test_mail_center.py::test_phase10_non_public_visibility_to_public_target_requires_human_release -q
```

Result: passed, 5 tests.

Additional dirty-state and Rust evidence commands:

```text
PYTHONPATH=src python -m digital_asset_directory.cli rust mail-spool-check
PYTHONPATH=src python -m digital_asset_directory.cli mail doctor --repo all --summary-only --fail-on-dirty
PYTHONPATH=src python -m digital_asset_directory.cli mail repair-plan --write-report --no-fail-on-blocked
```

Current live result: the Rust probe reported structural `issue_count=0`, and
the authoritative Python storm gate reported `spool_dirty=false`,
`worktree_dirty=true`, `safe_to_collect=true`, `safe_to_route=true`, and
`safe_to_deliver=false`. The remaining hold is reviewed delivery policy for
write-protected Logos repos, not mailbox corruption. The repair packet was
refreshed under `processed/reports/mail_storm_repair/`; its only active lane is
`delivery-policy-hold-review`, and it performs no mail lifecycle writes. The
three schema-invalid source-outbox rows that previously blocked the storm are
now quarantined by source-outbox path/hash as metadata-only records, so mutated
source rows would block again.

## Human Gates Still Pending

The following gates are not self-approved by this evidence:

- `phase-10-two-repo-mail-harness-reviewed`
- `phase-10-mailbox-write-boundary-reviewed`
- `phase-10-private-public-release-reviewed`
- `phase-10-duplicate-delivery-reviewed`

## Boundary

This packet is machine evidence for a synthetic mail trial. It does not prove
all real repo mailboxes are healthy, does not authorize broad delivery, and does
not satisfy public release or local adoption gates. Real repo waves still depend
on reviewed policy, clean mail doctor output, and human gate decisions.
