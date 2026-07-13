# Portfolio Attention V1

Status: implementation evidence for a read-only local portfolio scan. This is
not roadmap completion, cleanup approval, or cross-repo write authority.

## Problem

DAD's durable repo inventory records the current state of discovered checkouts,
but it does not enumerate every local branch and linked worktree or answer the
conditional attention question: "this project is active; which related dirty or
open work did I forget?"

The recovered portfolio OS plan also lacked implementation for branch/worktree
inventory, forgotten-work reminders, or HTML.

## Implemented Boundary

`asset-dir os status`:

- discovers canonical repositories under one or more local portfolio roots;
- handles an explicit aggregate Git root that also contains nested repos;
- groups all linked worktrees by Git common directory;
- inventories local branches, commit activity, upstream, ahead/behind, default
  branch, and ancestry-merged state;
- inventories dirty, staged, unstaged, untracked, conflicted, detached, locked,
  and prunable worktree metadata;
- detects an inactive branch inside an otherwise active project;
- emits explainable metadata-only related-project candidates with at least two
  shared signals;
- caps the HTML `Today` surface at three items while retaining the filterable
  full queue;
- writes local-private JSON and self-contained escaped HTML to DAD's report
  data plane.

It does not read source file contents for similarity, inspect raw chat, call a
model, create branches/worktrees/tasks, open editors, clean, delete, merge,
rebase, commit, push, or mutate source repositories.

## Live Evidence

Command scope:

```text
asset-dir os status --root "$HOME\OneDrive\Desktop\Git Projects" --max-depth 5 --stale-days 3
```

Initial correct full-scope run:

- wall time: `59.3s`;
- projects: `31`;
- local branches: `211`;
- linked worktrees: `121`;
- dirty worktrees observed: `27`;
- candidate attention items: `158`;
- scan errors: `0`.

The first attempt found only the aggregate workspace repo because the supplied
portfolio root was itself a Git checkout. A new synthetic regression test now
requires explicit aggregate roots to continue discovering nested projects.

## Performance Loop

Profiling by process shape showed redundant Git/process/filesystem latency:

- one ancestry process per branch;
- one status process per worktree, all serial.

The correction:

- uses one `git for-each-ref --merged=<default>` call per canonical repo;
- reads independent worktree status with a deterministically ordered,
  four-worker `ThreadPoolExecutor`.

Same live scope after correction:

- wall time: `33.69s`;
- projects: `31`;
- local branches: `211`;
- linked worktrees: `121`;
- scan errors: `0`.

That is approximately `43%` lower wall time. Git process and OneDrive/file-open
latency dominated, so a Rust rewrite was rejected. Rust remains appropriate
only if later profiling identifies a deterministic CPU/parsing hotspot with a
stable parity boundary.

The dirty/attention counts changed by one between the two live scans because
the portfolio is concurrently active; synthetic fixtures, not live count
equality, are the parity authority.

## Validation

Focused tests cover:

- dirty, inactive branch inside an active project;
- linked worktree grouping;
- aggregate Git root plus nested repo discovery;
- registered JSON Schema validation;
- DAD report output paths;
- explainable related-project candidates;
- HTML escaping;
- CLI discovery.

Focused result after independent review fixes:

```text
python -m pytest tests/test_portfolio_os.py tests/test_ai_navigation.py \
  tests/test_schema_conformance.py -q
51 passed

python -m ruff check src/digital_asset_directory/portfolio_os.py \
  src/digital_asset_directory/cli.py tests/test_portfolio_os.py
All checks passed
```

Branch-local DAD validation must name the isolated hub because the user-level
locator otherwise resolves the live main checkout:

```text
python -m digital_asset_directory.cli validate --hub .
valid=true, checked_count=229, warning_count=0

python -m digital_asset_directory.cli roadmap check --no-update --hub .
exit=0
```

The initial combined command omitted `--hub .`, followed the user locator to
the live DAD checkout, repeated expensive cross-repo observed-audit scans, and
timed out once at 64 seconds. A separate main-hub run completed in 118.74
seconds with pre-existing stale generated-evidence errors. The long-run review
measured the worktree validator at about 7.3 seconds and classified repeated
main-hub audits, Git/filesystem I/O, and output-at-end buffering as the real
cause. Invocation-local memoization is a candidate follow-up; no validator code
was changed in this slice.

`python -m pytest -q` was attempted once and exceeded the 300-second command
limit without producing a final result. It is recorded as not completed, not as
a pass. Focused changed-surface tests, schema conformance, navigation tests,
ruff, branch-local validation, roadmap checking, deterministic-repeat checks,
and independent checker fixtures provide the completed evidence for this slice.

The in-app browser rejected navigation to the local `file:` dashboard under its
URL security policy. Browser visual/interactive QA was not run; no alternate
browser or local-server workaround was used. Automated HTML escaping and DOM
filter code remain covered by source/test inspection only.

## False-Confidence Boundaries

- `merged_by_ancestry` is not proof that cleanup is safe; squash/rebase and
  semantic equivalence require later patch/PR evidence.
- A missing upstream is not an error by itself.
- Local absolute paths make the report `local_private_metadata` and
  `public_safe=false`.
- Remote identities remove URL/scp-style userinfo and drop URL query/fragment
  components so embedded credentials cannot enter JSON or HTML.
- A failed Git status probe becomes `dirty=null`, a scan error, and a priority
  attention item; it cannot silently become a clean worktree.
- Related-project scores are explainable candidates, not truth or dispatch
  authority.
- Dirty-file modification time is best-effort activity evidence, not proof of
  human work or intent.
- Scan time and state are point-in-time observations; a later branch/worktree
  action requires a fresh scan.
- No daemon schedule, Codex automation, plugin, hook, or persistent capture was
  enabled by this change.

## Reusable Lessons

1. A portfolio root may itself be an aggregate Git repo. Discovery must model
   the root and still inspect bounded nested projects.
2. Asset-catalog instance classification and human-attention classification are
   different planes: worktrees can be catalog noise but operationally urgent.
3. Preserve meaningful short domain tokens such as `OS`, `AI`, and `UI` in
   metadata relations while excluding generic commit boilerplate.
4. Batch Git ref queries and use bounded ordered concurrency before proposing a
   language rewrite for subprocess-heavy portfolio scans.
5. Daily attention should surface no more than three normal items; full detail
   remains available on demand.

Python tactic/idiom use:

- `python-functional-core-imperative-shell`: classification, ordering, and HTML
  rendering are separated from bounded Git and output side effects.
- `python-dataclass-value-object` and `py-idiom:dataclass-strict`: immutable,
  validated scan settings prevent loose option dictionaries across layers.

## Remaining Work

- Independent checker/red-team and full DAD validation.
- Durable Project/Idea/Workstream/SessionRef/ActivityEvent/ResumeCapsule schemas.
- Human snooze/pause state and batched daemon integration.
- Calibrated Background Connection Radar join and feedback loop.
- Human-gated archive assistant with ancestry, patch-equivalence, PR, conflict,
  and fresh-dirt evidence.
