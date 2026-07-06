# Phase 8 DAD Local Deployment Evidence

Created: 2026-07-04
Updated: 2026-07-06
Status: machine evidence captured; queued for human gate review

## Scope

This packet supports roadmap Phase 8, "Local DAD deployment and hub
resolution." It proves DAD can be called as a local-first hub from the DAD repo
and from non-DAD repos through a stable user-level shim and hub locator. The
roadmap now also declares the required machine command evidence so human review
alone cannot make this phase look complete.

This packet does not enroll target repos, deliver mail, approve public release,
or satisfy human gates by itself.

## Acceptance Mapping

| Requirement | Current evidence | Status |
|---|---|---|
| DAD can be installed or wrapped so `asset-dir` works outside the DAD checkout. | Bootstrap scripts create stable user-level shims under `~/.dad/bin`; live smoke used `asset-dir.ps1` from two temp non-DAD repos; deployment doctor now requires `external_invocation_ready` for `deployment_ready`; raw-checkout fallback is reported but is not Goal 1 acceptance. | machine-proven, human-review-pending |
| `--hub`, `DAD_HUB`, and user-level hub config resolve the same canonical DAD hub from non-DAD repos. | `tests/test_dad_local_deployment.py` covers explicit hub, `DAD_HUB`, locator, invalid-env fail-closed, and two non-DAD repo resolution. | machine-proven, human-review-pending |
| `asset-dir doctor` passes from DAD and at least two non-DAD repos. | Live deployment doctor passed from DAD with `--hub .`; live shim smoke passed from two temp non-DAD repos through the user locator with `inside_hub=false` and no target `processed/` writes; an additional read-only live smoke passed from Mock Trial4.26 and LawFirm-os-intake with unchanged git status before/after. | machine-proven, human-review-pending |
| `asset-dir agent preflight --repo .` works outside DAD. | Live shim smoke passed from a temp non-DAD repo, returned a context pack, wrote the session into the DAD hub, and did not create target `processed/` or `state/`. | machine-proven, human-review-pending |
| Unavailable DAD warns for ordinary local coding and fails closed for cross-repo writes, protected repo work, public release, enrollment apply/update, and sensitive mail. | `tests/test_dad_local_deployment.py` asserts the deployment doctor returns fail-closed hard gates when the hub is unavailable, representative `mail deliver` / `enroll apply` commands fail before target writes with controlled no-traceback output, and `dad unavailable-ack` can write a user-local audit row only when a named human reviewer is supplied. | machine-proven, human-review-pending |
| Recovery guidance is machine-readable without becoming a path-leak or mutable vocabulary. | `deployment.asset_dir.recovery_guidance.contract` freezes allowed missing-code and preferred-action values; operational readiness reports redact local command paths and retain only the non-sensitive contract plus a pointer back to `doctor --scope deployment`. | machine-proven, human-review-pending |
| Downstream agents know what to do when `asset-dir` is missing from `PATH`. | DAD front-door/agent instructions, downstream mailbox/exception/coding templates, generated mailbox README text, and enrollment contracts now route through the stable user shim at `~/.dad/bin/asset-dir` or `~/.dad/bin/asset-dir.ps1` before raw-checkout or metadata-only fallback. Focused tests pin those routes. | machine-proven, human-review-pending |

## Live Commands

Run from the DAD repo:

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli doctor --hub . --scope deployment --write-hub-locator
```

Result: passed. The deployment report showed `deployment_ready: true`,
`asset_dir.external_invocation_ready: true`, a valid hub locator, stable shim
availability, Python package availability, Rust toolchain availability, and the
unavailable-hub hard-gate policy. Child invocation probes now require valid
deployment JSON, successful temp locator write/readback evidence, a non-DAD
working directory, no inherited `PYTHONPATH`/`PYTHONHOME`, and real-hub module
attestation that the imported DAD operational module came from the resolved hub,
so an exit-zero fake wrapper or source-checkout parent shell cannot prove
deployment readiness by JSON alone. `--write-hub-locator` is also path-gated:
it may repair the user-level locator or DAD child-probe temp locator, but it
refuses caller-repo locator writes.

Run from two temporary non-DAD repos via the stable user shim:

```powershell
& "$HOME\.dad\bin\asset-dir.ps1" doctor --scope deployment
```

Result: passed in both temp repos. Both resolved the same hub through the
user-level locator, verified an external invocation path, and did not write
operational readiness reports into target repos.

Run from two real local non-DAD repos via the stable user shim:

```powershell
& "$HOME\.dad\bin\asset-dir.ps1" doctor --scope deployment
```

Repo labels:

- `mock-trial-4-26`
- `lawfirm-os-intake`

Result: passed in both real repos. Both resolved the same hub through the
user-level locator, reported `inside_hub=false`, and verified
`external_invocation_ready=true`. `git -c core.longpaths=true status
--porcelain=v1` was captured before and after the smoke; the status output was
unchanged in both repos, so the command did not mutate the target worktrees.
The tracked proof stores only repo labels and status hashes:

- `mock-trial-4-26`: before/after status SHA-256
  `ff3536ed377d29e799e43404e344ead6b26c04801bc089d4cfc6d8eaf40658ac`
- `lawfirm-os-intake`: before/after status SHA-256
  `160db6b45087726a018c473f4a4a625de3bbd745f32e94e154cd19e4f80d9c32`

This live smoke is callability evidence only and does not authorize enrollment,
mail delivery, or source-repo writes.

Run from a temporary non-DAD repo:

```powershell
& "$HOME\.dad\bin\asset-dir.ps1" agent preflight --repo . --agent codex --task "Goal 1 deployment smoke from outside DAD"
```

Result: passed. The preflight command used the DAD hub and returned a normal
context pack for the outside repo. The temp repo did not receive `processed/`
or `state/` writes.

Roadmap command evidence is recorded in `roadmap/gate-evidence.json` for:

- `python -m pytest tests/test_dad_local_deployment.py -q`;
- `python -m digital_asset_directory.cli doctor --hub . --scope deployment`;
- user-shim `asset-dir doctor --scope deployment` from two non-DAD repos;
- user-shim `asset-dir doctor --scope deployment` from Mock Trial4.26 and
  LawFirm-os-intake without target worktree changes;
- user-shim `asset-dir agent preflight --repo . --agent codex --task "Goal 1 deployment smoke from outside DAD"` from a non-DAD repo.

The same command set is mirrored in
`roadmap/evidence/phase-8-dad-local-deployment.commands.json` so future agents
can verify the machine-evidence contract without scraping prose.

## Human Review Packet

`roadmap/evidence/phase-8-dad-local-deployment.human-review-packet.json` is the
generated review packet for the four open Phase 8 human gates. It was produced
with:

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli roadmap human-gate-review-packet phase-8-dad-local-deployment --output roadmap/evidence/phase-8-dad-local-deployment.human-review-packet.json
```

The packet aligns the declared and computed roadmap state at
`awaiting_human_gate`, lists the exact machine evidence for human review, and
includes false-confidence warnings. It is review input only: it does not write
`roadmap/gate-evidence.json`, satisfy any human gate, approve public release,
authorize enrollment, deliver mail, or permit cross-repo writes.

## Focused Tests

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/test_dad_local_deployment.py -q
```

Result: passed, 40 tests.

Coverage includes:

- hub locator path, write, read, and validation;
- explicit `--hub` precedence;
- `DAD_HUB` and locator resolution from non-DAD repos;
- invalid env hub fail-closed behavior before locator fallback;
- hollow hub install-integrity rejection;
- raw-checkout fallback reported separately from external invocation proof;
- raw-checkout fallback does not satisfy Goal 1 deployment readiness by itself;
- external invocation probes scrub source-checkout Python environment variables
  and run from a temp non-DAD directory;
- deployment doctor from a non-DAD repo;
- same-hub resolution from two non-DAD repos;
- real user-shim subprocess doctor from two non-DAD repos without `DAD_HUB`;
- bare `asset-dir` from PATH when the user shim directory is on PATH;
- `agent preflight` from a non-DAD repo;
- real user-shim subprocess preflight from a non-DAD repo through the user locator;
- false-green wrapper output with nonzero exit code is rejected;
- false-green wrapper output with zero exit code but no probe locator writeback
  is rejected;
- false-green wrapper output that also writes the probe locator is rejected
  unless the child reports real-hub module attestation;
- explicit `--write-hub-locator --locator <caller-repo-path>` is rejected
  without mutating dirty or enrolled-looking target repo trees;
- direct `--skip-invocation-probes` cannot fake deployment readiness;
- deployment recovery guidance tells agents how to recover when `asset-dir`,
  user shims, PATH, or hub locator state are missing or stale;
- deployment recovery guidance includes a contract that limits allowed
  missing-code and preferred-action values;
- deployment recovery guidance uses the DAD hub as the bootstrap working
  directory so a target repo's own `scripts/` folder is not invoked by mistake;
- operational readiness reports redact local recovery command/path guidance and
  point agents back to `doctor --scope deployment` for local-only recovery
  commands while preserving the non-sensitive recovery contract;
- downstream DAD instruction surfaces try the stable user shim before raw
  checkout or metadata-only fallback when `asset-dir` is missing from `PATH`;
- unavailable-hub hard-gate policy;
- representative unavailable-hub write commands fail before target writes;
- unavailable-hub write commands return controlled errors without Rich
  tracebacks, `FileNotFoundError`, or target-local path leakage;
- `dad unavailable-ack` can write a named user-local audit row without a
  resolvable hub, but generic reviewer values such as `human`, `agent`,
  `codex`, or `claude` are rejected and do not write audit rows;
- additional hard-gated mail/enrollment commands fail before target writes when
  the hub is unavailable;
- bootstrap script shim generation order.

## Current Mail-Storm Snapshot

On 2026-07-05, `python -m digital_asset_directory.cli mail storm-gate
--no-fail-on-blocked` returned
`gate_status=mail_safe_delivery_policy_hold`, `spool_dirty=false`,
`worktree_dirty=true`, `safe_to_collect=true`, `safe_to_route=true`,
`safe_to_deliver=false`, and fingerprint
`sha256:62d1a6e1abd5e3c013f00fdba0558d1a976e05876320a4d2f2809be3252f22b1`.
The Rust leaf probe `python -m digital_asset_directory.cli rust
mail-spool-check` returned exit 0 with 83 checked files, 22 JSONL files, 54
Rust rollout packets, and zero malformed JSONL rows, oversized rows, lock
files, temp fragments, or Rust probe issues.

Interpretation: the live mail spool is structurally clean. The remaining
mail-storm hold is delivery policy for write-protected Logos repos, while the
large DAD git worktree remains ordinary worktree dirt. Repo agents should keep
writing candidate mail only to their own `.digital-asset/mail/outbox.jsonl`;
DAD may collect and route under reviewed policy, but should not deliver to
write-protected repos until repo-specific human review changes the policy.

A fresh read-only repair-plan handoff was written under
`processed/reports/mail_storm_repair/` with `latest.json` and `latest.md`
pointing to the current policy-hold packet. The repair plan performs no mail
lifecycle writes and does not approve delivery, public release, Rust snapshot
promotion, or target repo mutation.

## Current Caveats

- The bare `asset-dir` console script is not currently on PATH in the live
  environment, but stable user-level shims under `~/.dad/bin` work. This
  satisfies the current local deployment design, which allows either PATH
  install or stable wrapper. Raw checkout fallback is still useful for hub-local
  work but is not Goal 1 acceptance evidence.
- Human gates remain unverified until Lowell reviews this packet and records
  gate evidence in `roadmap/gate-evidence.json`.
- This evidence uses temporary repos and does not prove all-repo inventory,
  end-to-end mail, exception capture completeness, Rust production use, card
  catalog quality, or reviewed enrollment waves.

## Human Review Gates Still Open

- `phase-8-local-install-reviewed`
- `phase-8-hub-locator-reviewed`
- `phase-8-doctor-smoke-reviewed`
- `phase-8-unavailable-policy-reviewed`

## Boundary

Deployment readiness is callability evidence only. It does not scan source
repos, mutate source repos, approve public release, deliver mail, or authorize
enrollment.
