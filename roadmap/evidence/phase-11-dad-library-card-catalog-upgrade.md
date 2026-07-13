# Phase 11 DAD Library Card Catalog Evidence

Generated: 2026-07-12
Status: implementation evidence captured; human gates pending

## Authority boundary

This packet supports human review of the DAD-local catalog and context-pack
routes. It does not approve an offering, infer repository adoption, authorize a
target-repository write, enroll a repository, deliver mail, satisfy a human
gate, or promote Rust. Match scores and task-intent routes remain candidate
routing evidence under local repository authority.

## Implemented evidence

- All 16 current offerings declare nonempty `validation_refs`,
  `owner_authority`, and `adoption_semantics`.
- The offering schema accepts these fields while retaining compatibility with
  earlier `0.1.0` registry records.
- The usefulness methodology declares and versions its task-intent priority;
  match output reports the same routing basis instead of hiding precedence.
- Golden, paraphrased, negative, and multi-intent cases cover coding,
  governance, mail, Rust, and enrollment routes.
- Usage state distinguishes confirmed `depends_on` relationships from
  `dependency_candidate` observations.
- Candidate dependency rows do not become tracked usage or upgrade targets.
- `explicit_repo_record` dependencies require a source record.
- `human_reviewed` dependencies require a named non-generic human plus an
  adoption or review pointer. Agent and generic reviewer labels fail closed.
- Stable usage identity includes dependency basis and adoption identity, so a
  candidate and a reviewed dependency, or two distinct adoption reviews, do not
  collide.
- The public CLI exposes the dependency basis and enforces the same authority
  checks as the Python function.

## Validation

Passed:

- `python -m pytest tests/test_dad_library_control_plane.py -q` — 92 tests.
- `python -m pytest tests/test_ai_navigation.py -q` — 13 tests.
- Focused independent routing, schema-compatibility, dependency, CLI, authority,
  and collision probes.
- `python -m ruff check` for the changed Python and focused test files.
- `git diff --check` (line-ending warnings only).

Repository-wide `python -m digital_asset_directory.cli validate` did not pass.
It reported stale generated evidence associated with concurrent Mock Trial
changes, existing exception/observed-audit state, and generated reports whose
input hashes correctly changed after this Phase 11 repair. Those reports were
not refreshed by weakening or bypassing validation. Phase 9 inventory evidence
also remains deliberately unchanged because its authoritative stability window
detected concurrent target-repository activity.

## Review cautions

- `validation_refs` are declared evidence pointers. Their presence is not proof
  that every referenced suite exhaustively validates every use of an offering.
- Task-intent vocabulary is deliberately bounded and deterministic. It is not a
  general semantic model or adoption authority.
- A `dependency_candidate` remains candidate metadata until a source record or
  named human review creates a separate confirmed record.
- Current work supports human review; it does not self-satisfy any Phase 11
  gate.

## Human gates still pending

- `phase-11-offering-routes-reviewed`
- `phase-11-context-pack-golden-tasks-reviewed`
- `phase-11-offering-authority-reviewed`
- `phase-11-usage-ledger-reviewed`
