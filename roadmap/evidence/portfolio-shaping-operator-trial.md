# Portfolio Workstream Shaping Operator Trial

Date: 2026-07-13
Status: supervised local evidence; candidate-only activation
Method: `dad.portfolio-workstream-shaping.v1`

## Question

Can DAD turn the current sprawling portfolio into bounded split, rescope, possible-duplicate, and recovery choices without recording intent, exposing local paths, changing Git, or creating another daily queue?

## Trial boundary

The supervised command exercised the default scan path:

```text
asset-dir os shape
```

It refreshed derived Git attention, folded the existing workstream ledger, built strict cockpit and reconciliation snapshots, then published strict shaping JSON/HTML. No shaping decision event, binding, lifecycle change, branch/worktree change, task, schedule, notification, routine, MCP mutation tool, or agent dispatch was created. Scanner subprocesses retained `GIT_OPTIONAL_LOCKS=0`.

## Observed portfolio and result

| Measure | Count/result |
| --- | ---: |
| Projects | 31 |
| Branches | 234 |
| Worktrees | 145 |
| Attention items | 193 |
| Workstreams | 1 |
| Shaping cases | 153 |
| Hidden cases | 0 |
| Today shaping review | 3, all from cockpit Today |
| `RC0_integrity_unknown_attention` | 54 |
| `RC1_dirty_exact_attention` | 30 |
| `RC3_unassigned_observed_bundle` | 69 |
| Split/rescope/possible-duplicate cases | 0 |
| Source blockers | 0 |
| Source unknowns | 4 |
| `shaping_complete` | `false` |

All three sources were strict, current, and hash-coupled. Four unknowns remained visible in both JSON and the hardened HTML. Forty clean stale-only bundles were excluded after independent review proved that their earlier RC3 classification contradicted the no-age-only policy. One real workstream is insufficient to exercise split, rescope, or workstream-to-workstream duplicate precision, so their synthetic acceptance fixtures are implementation evidence, not operator precision evidence. The inventory is a collapsed review surface, not a second Today queue.

## Privacy discovery and correction

The first default trial failed closed before shaping publication. Four scanner access-error attention rows carried their local exception text into reconciliation bundle labels; the shaping semantic validator detected the embedded absolute paths as `raw_path_exposed` and rejected the cursor.

The first correction centralized path minimization at the shaping case/card boundary. Independent acceptance and red-team review then proved the deeper issue: confidential `idea_text` could be laundered through a field named `label`, and portable paths such as `/srv` or `/tmp` escaped the narrow detector. The final boundary no longer trusts any inherited display prose. Cases and cards use categorical labels; blockers and unknowns use controlled notes and opaque refs; source validation problems collapse to categorical codes; portable Windows, UNC, extended-Windows, POSIX-root, and home-relative path forms are rejected. Final shaping JSON and HTML each contained zero absolute-path matches and no raw `idea_text` value or conversation field.

This is a reusable boundary lesson: strict downstream projections must minimize inherited labels even when the upstream schema is valid, because display text can carry more sensitive provenance than its field name implies.

## Independent return review and hardening

Two bounded read-only reviewers reproduced no severity-0 issue, but found acceptance blockers and high-risk privacy/authority defects. The accepted fixes:

- persist and validate actual/claimed source coupling, then rebuild the full projection against the frozen sources before publication;
- bind every evidence tier to its exact case kind, disposition, canonical label, and canonical inert-choice vocabulary;
- publish bounded source-ID inventories and reject nonexistent case subjects;
- derive `status`, `shaping_complete`, and `intake_needed` semantically;
- suppress clean stale-only RC3 cases while retaining mixed age-plus-structural evidence;
- fail closed on malformed nested source maps;
- expose status, classification, source freshness, blockers, and unknowns prominently in HTML;
- catch ordinary late writer exceptions and restore all six dependent cursors;
- keep `os shape` and `os reconcile` source refreshes in memory rather than rewriting attention/workstream-state cursors.

The focused suite grew from 17 to 33 cases; a four-node CLI/rollback integration rung also passed. After excluding repo-local `.tmp` Git fixtures from portfolio discovery, the final six-module Portfolio authority suite passed all 171 cases in 83.7 seconds. Queue diversity, large-workstream pair-budget behavior, crash atomicity, and concurrent-reader generation switching remain deferred risks.

## Zero-write proof

The successful default-scan proof used atomic privacy-safe checkpoints for before, command receipt, and after state. It predates the independent return-review hardening; the final hardened build was additionally exercised with `os shape --no-scan-portfolio`, which now keeps its attention and workstream-state sources in memory. It compared:

- 31 common project surfaces: HEAD, config, packed/loose refs, and lock presence;
- 145 linked worktree surfaces: porcelain-v2 status, index bytes/mtime, worktree HEAD, and lock presence;
- the exact append-only workstream ledger bytes, size, and mtime;
- four discovery errors represented only by opaque hashes.

Results:

- command exit code: `0`
- project surface sets unchanged: `true`
- changed project surfaces: `0`
- worktree surface sets unchanged: `true`
- changed worktree surfaces: `0`
- ledger bytes and modification time unchanged: `true`
- discovery-error hashes unchanged: `true`
- absolute path matches in shaping JSON: `0`
- absolute path matches in shaping HTML: `0`
- raw conversation field present: `false`

The pre-return-review aggregate proof is retained locally at `.tmp/shaping-zero-write-proof-current.json`; resumable component checkpoints sit beside it. They contain opaque hashes and counts, not paths, Git output, remote values, error text, or command output.

A prior 121.9-second proof wrapper is explicitly inconclusive: it completed expensive observations but crashed after assuming a legacy cursor path, and its in-memory snapshots were unrecoverable. No value from that attempt is relabeled as same-run proof. The corrected wrapper parses the CLI path, checkpoints every phase, and completed in 47.3 seconds. That optimization changes evidence orchestration only, not shaping policy.

## Confirmed findings

- Candidate-only recovery shaping can reuse exact cockpit Today anchors without expanding the daily queue.
- Integrity-unknown recovery must restrict choices to inspect/defer.
- Age can remain annotation without becoming a neglect or priority claim; 40 clean stale-only bundles were removed from the final live inventory.
- Inherited display labels require a privacy boundary even when all source schemas pass.
- Synthetic Git fixtures must live outside discovery coverage or in an explicitly excluded directory; `.tmp` is now excluded and protected by a regression test.
- Source-hash coupling plus semantic validation prevents stale dependent cursors from generating cases.
- Six-file synchronous rollback protects prior cursors even when an ordinary runtime failure is injected in the final writer after earlier replacements; this does not prove crash atomicity.
- The command changed no observed Git or ledger surface in this supervised run.

## Inferred findings

- Most current value is recovery and intake triage; split/rescope/duplicate operator value cannot be estimated until more workstreams have reviewed exact scope.
- The 153-case inventory will likely need filtering, per-workstream hidden counts, or pagination before recurring activation.
- Asset review classified static-projection safety as an `improve_existing` harness family and resumable zero-write proof as an extension of the existing read-only inventory family; neither is promotion-ready yet.

## Assumptions, unknowns, and activation decision

- The portfolio count rose from the earlier reconciliation trial because the later default scan observed 234 branches and 145 worktrees. This trial treats the new snapshot as observed evidence and does not infer why topology changed.
- Four source unknowns remain, so shaping correctly stays partial.
- OneDrive crash interruption and active concurrent lock contention remain untested.
- Stable hashes detect local drift; they are not signatures or authenticity proof.
- No durable choice/defer/reject history exists yet.

Keep shaping supervised and candidate-only. Do not enable the daily routine, durable shaping-decision event, or any executor. Collect human labels for useful/noisy recovery rows, missed scope boundaries, and inventory burden first.

## Validation

Final local evidence:

- focused shaping: 33 passed;
- CLI/publication rollback rung: 4 passed;
- Portfolio authority suite across shaping, scanner, workstreams, cockpit, reconciliation, and navigation: 171 passed in 83.7 seconds;
- Ruff and `git diff --check`: clean (line-ending warnings only);
- live strict/semantic shaping cursor: zero semantic problems, zero JSON/HTML absolute-path matches, partial banner and Unknowns section present;
- roadmap check: exit 0;
- full DAD validator: 852 surfaces checked and 52 unrelated stale exception/report/graph artifacts reported; the shaping schema, navigation cap, and Portfolio tests passed.

The in-app browser refused the local `file://` report under its URL security policy, so visual screenshot inspection was not run. No alternate-browser or local-server workaround was attempted. Structural HTML, CSP, escaping, partial-state, source-readiness, unknowns, and privacy assertions passed.
