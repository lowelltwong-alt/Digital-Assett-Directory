# Phase 9: All-Repo Read-Only Inventory Evidence

Generated: 2026-07-12
Status: stable local machine evidence captured; GitHub coverage incomplete; human gates still pending

## Scope

This evidence covers the Goal 2 read-only inventory/classification slice from
`roadmap/evidence/dad-deployment-and-all-repo-verification-roadmap.md`.

DAD generated central-only inventory reports under:

- `processed/repo_inventory/reconciled_inventory.json`
- `processed/repo_inventory/reconciled_inventory.md`

No target repo enrollment, mailbox delivery, source edits, hook install, or
governance apply/update was run.

## Implemented Safeguards

- `enroll` now requires a reviewed enrollment policy; a mail policy alone no
  longer implies enrollment authority.
- Enrollment policy is preferred over mail policy for inventory decisions, so
  active holds, dirty/non-main gates, and local-path permissions are not masked.
- Public-facing records from policy or repo contract use `dad://repo/...` refs
  and redact branch/head/remote details unless local paths are explicitly
  allowed.
- GitHub rows are not merged into local repos by basename alone; a verified
  GitHub `origin` remote match is required.
- Enabled GitHub sources without imported repo rows are marked incomplete
  instead of implying all-GitHub coverage.
- Nested Git roots are visible and classified conservatively, while workspace
  root Git metadata does not make every child repo look nested.
- Pytest temp workspaces are skipped from repo discovery.
- Rust build `target` directories, symlinked directory repos, and Windows
  junction/reparse directory repos are not treated as enrollable repo roots when
  `follow_symlinks=false`.
- Rust repo-inventory shadow parity compares both discovered repo roots and the
  skipped-directory safety surface, so it cannot report `matched` while Python
  and Rust disagree about pruning `.git`, `target`, cache, or temp directories.
- The durable reconciled inventory now includes a content fingerprint and derives
  `report_id` from stable report content, not just hub path plus repo count, so
  same-count inventory changes cannot reuse the same report identity.

## Current Authoritative Quiet-Window Inventory

On 2026-07-12, a fresh authoritative run captured a Git-state fingerprint for
every discovered repository, reconciled the inventory, rediscovered the same
scope, and captured the same fingerprints again. The snapshot included the
current commit or `UNBORN` sentinel, porcelain status, and bounded content
signatures for changed and untracked paths. Git subprocesses were parallelized
only for the read-only before/after snapshots; inventory reconciliation remained
single-authority and target repositories were never run concurrently against a
competing implementation.

Quiet-window result:

- before repository count: 82
- after repository count: 82
- repositories with changed Git state: 0
- before fingerprint:
  `sha256:e009b6d9e5fb81afb7f1d29040250b69f1b4f7812a824144863ed891f47fcec6`
- after fingerprint:
  `sha256:e009b6d9e5fb81afb7f1d29040250b69f1b4f7812a824144863ed891f47fcec6`
- unavailable Git-state fingerprints: 0
- elapsed time: 118.452 seconds
  - before snapshot: 64.278 seconds
  - inventory reconciliation: 40.640 seconds
  - after snapshot: 13.534 seconds

An earlier attempt timed out after 304.1 seconds before it could emit a
stability verdict. It is rejected evidence. It did not update this packet. The
accepted rerun removed redundant sequential Git subprocesses while preserving
the same fail-closed before/inventory/after comparison.

## Current Durable Inventory Smoke

Command:

```text
PYTHONPATH=src python -m digital_asset_directory.cli dad inventory --max-depth 5
PYTHONPATH=src python -m digital_asset_directory.cli rust repo-inventory-probe --max-depth 5
PYTHONPATH=src python -m digital_asset_directory.cli rust repo-inventory-parity --max-depth 5
```

Result:

- GitHub connector import rows: not present in the durable current config
- GitHub coverage status: `configured_disabled`
- GitHub coverage complete: `false`
- report content fingerprint:
  `sha256:d46d43f14250094d25412b4bc087d38793dabc44cd303a9cde6f11b6a15ebdac`
- repo_count: 82
- classification_counts:
  - active-no-write: 9
  - duplicate-ignore: 55
  - enroll: 1
  - needs-human-classification: 10
  - protected-central-only: 7
- public-facing records checked: 18
- public-facing local-path leak check: clean; no user-home or OneDrive fragments
- unresolved candidate dispositions are represented only by these opaque central
  record aliases; no local paths are included:
  - `dad:dad-repo-record:dd582769-31d4-5331-a241-e39c0d757a72`
  - `dad:dad-repo-record:ee569709-e407-541f-99f0-f771e9b3f793`
  - `dad:dad-repo-record:87531b10-0c07-5b5d-939a-57c0f3429bca`
  - `dad:dad-repo-record:0786d403-79b5-5fdd-b845-3a7b918fbe6c`
  - `dad:dad-repo-record:663fccb5-4028-5797-a2d0-cb48e474df18`
  - `dad:dad-repo-record:5841ab90-798a-5649-8d19-f56e506db514`
  - `dad:dad-repo-record:bc6aa7c6-ab22-52bc-89d2-6646d3344deb`
  - `dad:dad-repo-record:e7efe4e0-a014-5527-a831-a5cbe128cd2c`
  - `dad:dad-repo-record:bc8ab4bb-7ef1-51fe-868d-e37f1e632f67`
  - `dad:dad-repo-record:558ef48a-b8f8-5a91-884d-705bbfe77dc3`
- pytest temp, Rust `target`, symlink, and junction traversal checks: clean
- Rust repo-inventory probe: read-only, alias-only structural evidence for
  configured local roots; Python remains the authority for classification,
  GitHub reconciliation, public-safe redaction, policy holds, and human gates.
- Rust/Python shadow parity below is retained prior structural evidence from the
  2026-07-05 48-repository corpus. It was not rerun against the current
  82-repository corpus and therefore does not establish current-corpus parity.
  - prior Python repo roots: 48
  - prior Rust repo roots: 48
  - prior matched repo roots: 48
  - Python skipped dirs: 255
  - Rust skipped dirs: 255
  - skip-policy mismatches: 0
  - duplicate logical paths: 0
  - contract-present mismatches: 0

Historical note: an earlier smoke used a temporary `.tmp/phase9_sources.with-github.yaml`
file with imported GitHub rows. That was useful exploratory evidence, but it is
not the durable current inventory source. The current checked-in evidence must
not imply all-GitHub coverage until reviewed GitHub rows are imported through a
durable source.

Current special-repo checks:

- DAD is `active-no-write` because the current worktree is dirty.
- Mock Trial/Albert is `active-no-write`, not Logos-protected.
- Logos Scripture Graph is `protected-central-only`.
- Logos Governance Architecture is `protected-central-only`.
- GitHub-only archived and non-archived rows are not evaluated in the durable
  current run because GitHub repo rows are not currently imported into a
  reviewed checked-in source.

## Review Lane Findings

Red-team/premortem sidecar found and this patch addressed:

- mail policy masking enrollment holds;
- public-facing contract rows leaking local paths when policy is absent;
- unsafe GitHub basename-only reconciliation;
- GitHub configured-source false coverage;
- nested Git roots being hidden.

Lesson/asset/harness scout recommended:

- `lesson:dad-goal2-readonly-inventory-is-not-enrollment`;
- a candidate `harness:goal2-readonly-inventory-classification`;
- carrying forward that central DAD triage is not human release or target
  repo adoption.

## Validation

Current authoritative validation:

```text
optimized read-only Git fingerprint snapshot
PYTHONPATH=src reconcile_repo_inventory(..., max_depth=5)
optimized read-only Git fingerprint snapshot
```

Result: 82/82 repositories were present before and after; the aggregate
fingerprints matched; zero repository states changed; zero fingerprints were
unavailable; public-safe scanning found zero private-path fragments. GitHub
coverage remains deliberately `configured_disabled` and incomplete. No GitHub
credentials or connector rows were used.

The following commands are retained as prior structural validation from the
earlier packet and are not claimed as fresh 82-repository results:

Commands run:

```text
PYTHONPATH=src python -m pytest tests/test_dad_library_control_plane.py -q
PYTHONPATH=src python -m pytest tests/test_dad_library_control_plane.py::test_inventory_report_id_changes_for_same_count_content_change -q
PYTHONPATH=src python -m pytest tests/test_dad_library_control_plane.py -k "repo_inventory_rust_probe_parity or inventory_skips_rust_target or symlinked_repo" -q
PYTHONPATH=src python -m pytest tests/test_rust_bridge_dad_scan_core.py::test_run_dad_repo_inventory_probe_rejects_duplicate_root_aliases_before_cargo -q
cargo test --manifest-path tools/dad_scan_core/Cargo.toml repo_inventory_probe -- --nocapture
PYTHONPATH=src python -m ruff check src/digital_asset_directory/dad_library.py tests/test_dad_library_control_plane.py
PYTHONPATH=src python -m digital_asset_directory.cli dad inventory --max-depth 5
PYTHONPATH=src python -m digital_asset_directory.cli rust repo-inventory-probe --max-depth 5
PYTHONPATH=src python -m digital_asset_directory.cli rust repo-inventory-parity --max-depth 5
PYTHONPATH=src python -m digital_asset_directory.cli mail doctor --repo all --summary-only
```

Results:

- focused parity/skip-policy tests: passed;
- Rust repo-inventory tests: passed, including public-safe segment
  normalization, duplicate alias rejection, and deterministic skipped dirs;
- inventory command with durable current config: passed;
- Rust repo-inventory probe: passed as read-only structural evidence;
- Rust/Python repo-inventory parity: `matched`;
- mail doctor with `--repo all --summary-only`: blocked by known mailbox
  dirty-state issues; this does not change Phase 9 inventory evidence and does
  block collect/route/deliver until repaired or quarantined.

## Human Gates Still Pending

The following gates are not self-approved by this evidence:

- `phase-9-inventory-scope-reviewed`
- `phase-9-classification-reviewed`
- `phase-9-protected-active-rules-reviewed`
- `phase-9-public-safe-report-reviewed`

This evidence supports review. It does not authorize broad enrollment or
target repo writes.
