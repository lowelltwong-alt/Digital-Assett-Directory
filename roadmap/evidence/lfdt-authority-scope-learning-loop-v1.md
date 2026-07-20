# LFDT authority and PR-scope learning loop v1

Status: observed candidate; trigger watch only; not an enabled automation  
Date: 2026-07-20  
Source repository: `law-firm-digital-twin`  
DAD lesson: `dad:lesson:ff023194-14a8-5ccd-b6af-6bb2cd53af1e`

## Observable incident

A private execution handoff interpreted a later natural-language instruction as
authority to publish and merge a C023 source-lineage commit. The committed Gate A
packet remained more specific: create one exact 14-file source commit and stop,
with publication and target-branch admission withheld pending Gate B.

The local C023 commit itself was correct and independently validated. The error
occurred at the next boundary: a pull request was opened before comparing the
full PR diff against the real remote base and the committed authority packet.
Because three dependency commits were not on `main`, the one-commit local change
produced a four-commit, 35-file PR rather than the approved 14-file scope.

## Containment and verified result

1. The PR was converted to draft when the full remote-base diff was observed.
2. The committed packet and derived handoff were compared directly.
3. An independent architecture review confirmed that the committed packet
   controlled and the derived handoff could not silently broaden it.
4. PR 2 was closed without merge:
   `https://github.com/lowelltwong-alt/law-firm-digital-twin/pull/2`.
5. The immutable C023 source branch and commit
   `b263d13a1f91529d489e2b3de95da3861abe5ef0` were retained.
6. The independently accepted two-file W1 commit
   `cb9546d0ed71ee8c329171138e16608e9af032c1` remained local and unpushed
   because its remote-base diff would also include an unmerged ancestor.
7. No force push, history rewrite, branch deletion, or dirty-root mutation was
   used.

The observable safety result is that no over-scoped commit reached `main`.

## Reusable lesson

Before push, PR creation, ready transition, or merge, resolve source authority
and explicit supersession first, then compare the complete proposed PR commit
set and path set against the real remote base and approved scope. A local commit
diff is not evidence of PR scope when its ancestors are absent from the base.

Derived handoffs are coordination evidence. They do not silently override a
more specific committed packet. A later human instruction supersedes an earlier
record only when the applicable policy accepts that authority and the approval
is bound to the relevant revision, action, head, base, and scope.

## Applicability limits

Applies when:

- an external Git action is proposed;
- committed authority, approval, admission, release, or exact-scope records
  exist;
- a private/derived handoff or natural-language paraphrase is being used; or
- the proposed branch contains ancestors not present on the real remote base.

Does not apply when:

- no external Git action is proposed;
- no authority or scope artifact exists and the action remains human-blocked; or
- a later revision-bound human approval explicitly supersedes the earlier
  record and matches the exact action, head, base, commit set, and path set.

Danger if misapplied:

- under-enforcement can publish or merge unauthorized scope;
- over-enforcement can block a legitimate, explicit later approval;
- treating all later language as invalid would replace human authority with an
  automated veto; and
- treating all later language as sufficient would make committed gates
  meaningless.

## Dedupe decision

Searched surfaces:

- the Trigger Pattern Taxonomy;
- existing trigger-radar routines;
- DAD source-authority conflict and exception guidance;
- deterministic learning rules for context-bound lessons and observable
  decision traces; and
- existing branch/workstream mismatch, dependency discovery, validation-gap,
  trigger-miss, and learning-loop-gap families.

Broader matches were retained as taxonomy links, not duplicated:

- `dependency discovery` covers the absent-ancestor signal but not authority
  supersession;
- `validation gap` covers missing evidence but not exact approved PR scope;
- `trigger miss` describes this incident but not the preventive gate;
- `branch/workstream mismatch` describes mixed outcomes but not publication
  authority; and
- `source_authority_conflict` is a valid stop class but lacks the ordered
  pre-publication Git comparison and suppression contract.

The novel reusable composition is the boundary between authority precedence,
explicit supersession, and the complete remote-base PR diff immediately before
an external Git action. No existing routine combines those signals,
suppressors, deterministic checks, semantic-AI limit, and human gate.

Rejected alternatives:

- a generic “always trust committed files” rule would incorrectly block valid
  later revision-bound human approvals;
- a generic “latest instruction wins” rule would erase committed gates; and
- a model-only semantic reviewer would be weaker than deterministic identity,
  ancestry, and path-set checks.

## Preventive trigger and AI boundary

The watch candidate
`dad:trigger-pattern:pre-publication-authority-scope-conflict` uses this order:

1. Deterministically identify repository, remote, proposed action, head, and
   real remote base.
2. Deterministically locate committed authority revisions, approval scopes, and
   explicit supersession references.
3. Deterministically compute the full PR commit and path sets.
4. Compare those sets with the approved allowlist and dependency order.
5. Suppress when exact supersession and scope equality are proven.
6. Use an AI semantic judge only when natural-language supersession remains
   ambiguous. The model may classify and draft a conflict packet, but it may
   not authorize an action.
7. Require a named human decision before push, PR mutation, ready transition,
   merge, history rewrite, branch deletion, or instruction change.

The first incident supports `watching`, not promotion. Historical replay,
negative cases, lineage-distinct occurrences, false-positive review, and human
approval are still required before notification or hook activation.

## Processing and evidence

- LFDT postflight handoff:
  `dad:handoff:0e3c9db6-49d1-55f4-b154-7caa1204635f`
- LFDT postflight lesson:
  `dad:lesson:78e10a42-0199-56ee-a9c5-8c0702d145ce`
- Active-hub normalized authority lesson:
  `dad:lesson:ff023194-14a8-5ccd-b6af-6bb2cd53af1e`
- PowerShell/Typer list-option capture lesson:
  `dad:lesson:31dc8f18-df84-5d2f-956b-3cb90c914130`
- Trigger specification:
  `assets/agent-skills/dad-trigger-pattern-radar/routines.yaml`
- Deterministic contract test:
  `tests/test_ai_native_process_pilot_contract.py`

All retained evidence is privacy-safe metadata. Private handoff text, raw
conversation content, secrets, and payloads are excluded.

An isolated processing trial exposed that PowerShell comma expressions can
fragment list-valued CLI fields. That trial remained isolated and did not enter
the active hub. The active-hub lessons use atomic capability and reusable-pattern
identifiers. DAD reindexed 1,441 active lessons and rebuilt a 1,641-node,
1,452-edge lesson graph. The graph remains candidate evidence and grants no
trigger activation or source-repository authority.
