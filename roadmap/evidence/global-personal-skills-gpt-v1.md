# Global Personal Skills GPT V1 Evidence And Handoff

Risk tier: high. Human gate: Lowell explicitly authorized implementation,
validation, publication, independent review, merge after passing checks, and
creation of the daily automation after the command/tests pass.

## Decision

Chosen option A: a focused archive module, schemas, CLI, local-only state, and
candidate graph, integrated with the existing Agent Skill Library only for the
reviewed steward/adaptation package.

Rejected option B: using the Agent Skill Library or checkout ledger as raw
snapshot storage. That would make inert copies look adoptable and risk a second
active source.

Defer/do-nothing remains the fail-closed result whenever an initialized data
root, explicit allowlist, safe revision, export approval, validation, PR check,
or independent review is missing.

## Blast Radius And Bounded Comparison

Affected surfaces: new CLI contracts, four schemas, source allowlist, transport
path registry, control-plane registry, two edge registries, agent-skill library,
navigation/docs, local graph, tests, PR workflow, and daily automation.

The bounded comparison used correctness, false-positive/negative risk, review
burden, privacy, source authority, determinism, rollback, and future-agent
overtrust. Option A isolates storage and produces testable invariants. Option B
conflates archival evidence with skill adoption. Defer avoids leakage but leaves
no governed history or portability path.

## Implementer Red Team And Premortem

Primary failure modes:

- a new third-party directory is mistaken for personal and archived;
- an encoded or novel secret evades best-effort screening;
- a link, junction, normalized-path collision, or mid-read edit escapes scope;
- an archive surface is accidentally included in Git journal replication;
- a future agent treats hash equality, latest pointer, `portable_to`, or a DAD
  adaptation as approval/canon/installation;
- automation runs from an obsolete worktree whose marker does not match and
  writes legacy state;
- automatic portability changes runtime-specific semantics silently.

Controls: explicit allowlist/default deny, deny-wins, metadata-only unknowns,
whole-revision blocking, regular-file/link checks, before/after stat check,
local-only surface outside journal scope, initialized-root recurring-write gate,
candidate-only graph language, named export approval, fixed deterministic ZIP,
path redaction plus fail-closed residual scan, and stable post-merge automation.

Six-month premortem: without those controls a third-party skill containing a
credential is archived, journaled, exported as "portable", and installed beside
the live source while stale-worktree automation creates competing state. The
present design kills the chain at allowlist, unsafe revision, journal boundary,
export review, and initialized-root gates.

## Independent Fresh-Eyes Review

The read-only Terra/high-equivalent reviewer returned conditional GO for option
A and rejection of option B. Its key missed effect was that `journal.py`
checkpoints every `DATA_PLANE_PATHS` surface. The design changed before coding:
archive bodies now use `LOCAL_ONLY_DATA_PATHS`; migration sees the union but the
journal sees only journaled paths. The reviewer also required default-deny
origins, two-pass stability evidence, whole-revision quarantine, no automatic
`supersedes`, reviewed exports, and stable-hub automation.

The read-only Luna/medium-equivalent scout confirmed reusable current patterns:
Typer sub-apps, transport marker fallback, stable IDs, append-only JSONL,
content hashes, skill-package shape, dual edge registries, and existing
`personal-skill-source:*` adaptation markers. Historical branch
`codex/register-personal-skill-sources` supplied concepts only; current main
already contains its six runtime-neutral adaptations. No historical code was
copied and no parallel harness compatibility schema was inspected or edited.

## Independent Gate Hardening

The initial independent code/privacy gate requested stronger fail-closed
integrity. The implementation now prevalidates an entire snapshot and its
collision set before writes; writes immutable blobs/revisions before the run
record, append logs, and mutable pointers; validates revision IDs, ownership,
tree/blob hashes, source runtime, and contained archive paths on every reuse;
and reconciles orphaned pointers without deleting history. Reads use
link-resistant open plus before/after file-identity checks. Production CLI
commands cannot override the governed source root or manifest.

The same gate expanded export screening to Windows, UNC, home, and POSIX
absolute paths in both metadata and member bytes; validated ZIP member paths
and source-runtime identifiers; bound each export to the requested skill and
revision; and made historical, stale, unsafe, unknown-origin, unvalidated,
adaptation, and duplicate query roles explicit. Graph snapshots now point to
immutable source-observation nodes, while only current observations can emit
`loaded_by`.

The final gate then demonstrated a redirected pointer namespace. Every archive
write now rejects link, junction, and reparse-point ancestors from the data root
through the exact output path immediately before mutation. The invariant covers
blobs, revisions, pointers, run records, append logs, exports, graph output, and
the snapshot lock; the exact live-source redirection is a regression test.


A second fresh gate found that `.env` normalization was nonblocking, migration
did not yet reject redirected source/destination ancestors, and graph skill IDs
were double-prefixed. The fixes make `.env` whole-revision blocking, extend the
non-link/reparse invariant through copy-verify migration, and preserve the
registered `personal-skill:*` identity exactly once; each has regression evidence.
## Provenance

- Original isolated-worktree base: `7b3155341e3f221f7af730b8ef82f0234db50114`;
  rebased and validated against remote `main` `28826ce8e8319f2825d797bdf25f0f95c6ab2198`.
- Implementation owner: Codex, GPT-5 family, orchestrator at Terra/high-equivalent effort.
- Independent lanes: Luna/medium pattern scout; Terra/high architecture reviewer;
  Terra/high algorithm/runtime long-run reviewers; separate code/privacy gate.
- Edit provenance: generated from Lowell's brief and current repository patterns;
  historical Git branch inspected read-only for conceptual provenance.
- External code: none imported.
- Python tactic used: `py-idiom:dataclass-strict` for immutable keyword-only
  observation records; not used at schema boundaries where JSON Schema remains
  authoritative.
- Reviewed lesson reuse: `dad:rust-rollout-lesson:346c1ce4-21bb-5e3c-852e-62a59b39fb39`
  shaped whole-plan validation before writes;
  `dad:rust-rollout-lesson:c532172d-32be-5128-9618-ab6251f7b97f` shaped
  sensitive fingerprint screening; and
  `dad:rust-rollout-lesson:cfd7ad21-208d-5a30-ba28-f86b82c9d4d6` shaped
  root/nested exclusion. All remain context-bounded candidate reuse evidence.

## Validation And Promotion Gates

Required before merge: focused archive tests, schema conformance, agent-skill
library validator, graph/transport tests, `asset-dir validate`, roadmap check,
focused and related non-network pytest, independent code/privacy checker, PR checks, unchanged
head SHA, and no unresolved review thread.

Kill criteria: live-skill mutation, excluded-body read, archive bytes in journal,
absolute path in graph/export, unstable revision, blob/revision collision,
schema drift, failing check, or changed PR head. Rollback disables automation
and reverts the code/registry routes without deleting historical archive state.

## Validation Evidence

- Focused archive/security/export/graph/data-root suite: 32 passed.
- Related schema, navigation, agent-skill, graph-journal, graph-registry, and
  targeted transport suite: 92 passed.
- `python -m ruff check` on every changed Python file: passed.
- Python compile smoke, 12 JSON parses, two YAML parses, and
  `scripts/validate_agent_skill_library.py`: passed; 15 skills validated.
- `python -m digital_asset_directory.cli validate --hub .`: passed with 232
  checks, zero warnings, and zero errors.
- `python -m digital_asset_directory.cli roadmap check --no-update --hub .`:
  passed. Existing phase gate states remain evidence-bound and were not changed.
- Live read-only `personal-skills status --hub .`: 20 allowlisted active skills,
  zero unsafe, zero missing, zero unknown-origin, one generated cache exclusion,
  and no local absolute path in the public status rows.

The first validator attempt omitted `--hub .`; the user hub locator therefore
routed it to the operational dirty checkout and inherited stale generated
reports. The long-run pack measured 62.5 seconds there and 59.3 seconds on the
untouched baseline. Independent branch validation with `--hub .` ran in about
3.2 seconds and passed. The performance director classified the operational
cost as repeated filesystem audit I/O and recommended a separate experiment in
invocation-local memoization with exact parity; Rust, concurrency, persistent
caching, and any optimization change in this feature were deferred.


## Handoff

Operators use `asset-dir personal-skills status` first. Initialize/migrate the
stable hub data root before `daily`. Review unsafe and unknown-origin metadata;
never broaden the allowlist from a model suggestion alone. Export only one
reviewed revision at a time with reviewer and approval IDs. The next review is
triggered by a new runtime adapter shape, binary/reference inclusion request,
journal/backup policy change, allowlist change, or repeated screening failure.
