# D19 — Disposition of the stale intake copy "A"

Status: **OPEN — mechanical action blocked by a Windows file lock**
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

## Resolution

(unfilled)
