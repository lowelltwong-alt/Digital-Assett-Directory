# D19 — Disposition of the stale intake copy "A"

Status: **RESOLVED 2026-07-27 — archived; the file lock cleared**
Raised: 2026-07-09 by Fable (boss); trap first documented 2026-06-24
Owner: Lowell T. Wong

## Question

When and how is `00_LawFirm_OS\LawFirm-os-intake` ("A") archived so no agent ever edits it again?

## Facts

- A is a stale snapshot (~74 schemas / 38 modules vs B's ~420 / ~152); it resolves to the
  aggregate root git repo, not a tracking clone. Editing A and running tests silently tests B.
- A currently contains the ONLY copies of the DAD-layer handoff docs (`docs/ai-handoff/*DAD*`,
  `HARD_KERNELS_FOR_FABLE_DAD_LAYER.md`) — ported to B by task T-0001 before any archival.
- A marker `_ARCHIVED_DO_NOT_USE.md` exists in A. A rename to
  `LawFirm-os-intake.ARCHIVED-2026-06-23-snapshot` was previously blocked by a process holding
  the folder open (OneDrive/indexer suspected).

## Sequence required

1. T-0001 merges (docs ported to B, with correction headers).
2. Human closes the locking process (or reboots) and renames A to
   `LawFirm-os-intake.ARCHIVED-2026-06-23-snapshot`.
3. Root `docs/` note updated so the workspace maps stop pointing at A.

## Safe placeholder

Marker file stays; every spec and roadmap in this home names B as the only intake target;
`START_HERE.md` step 4 forbids A explicitly.

## Risk if guessed

An agent (or Fable itself in a future session) re-ingests A's stale diagnosis or lands work in
an untracked tree that can never reach GitHub.

## Resolution — 2026-07-27

Executed during the Wave 0–2 publication run. The lock that blocked the rename since 2026-06-24
had cleared; the rename succeeded on the first attempt.

**Actions taken**

1. `00_LawFirm_OS\LawFirm-os-intake` → `00_LawFirm_OS\LawFirm-os-intake.ARCHIVED-2026-06-23-snapshot`.
2. Verified B is unaffected: 436 schemas intact, and the editable install re-resolves to
   `repos\LawFirm-os-intake-seed-clean-20260623\src\lawfirm_os_intake`.
3. Verified the parent aggregate repo tracked **0** files under the old path, so no git state moved.
4. Root workspace docs checked: no map, front door, or README pointed at A. Nothing to update.
5. The `_ARCHIVED_DO_NOT_USE.md` marker travels with the archived directory.

**Precondition satisfied**

Sequence step 1 (T-0001, docs ported to B) had already landed. The DAD-layer handoff docs are now
in B on **both** `main` and `feat/port-dad-layer-docs`, including
`LAW_FIRM_OS_DAD_LAYER_ARCHITECTURE_PLAN.md`, `HARD_KERNELS_FOR_FABLE_DAD_LAYER.md`,
`FABLE_MASTER_ARCHITECT_DAD_LAYER_PROMPT.md`, and `OPUS_4_8_DAD_LAYER_INTAKE_PROMPT.md` —
so archiving A destroys no unique content.

**Material change since this record was written:** intake B is now a **public** repository
(`lowelltwong-alt/LawFirm-os-intake`, released 2026-07-27 under
`USER-2026-07-27-INTAKE-PUBLIC-RELEASE`). The A/B trap is correspondingly less dangerous — B is
now the copy with a public remote and CI — but the archive still matters, because A is an
untracked local tree from which work could never reach GitHub at all.

**Residual:** the archived directory remains on disk rather than being deleted, so the snapshot
is still recoverable if some artifact turns out to be unique to it. Deleting it is a separate,
later call.
