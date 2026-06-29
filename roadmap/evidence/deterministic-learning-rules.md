# Deterministic Learning Rules Evidence

Status: reviewed operating-rule seed for future agents; no roadmap phase is completed by this file.

Generated on: 2026-06-25

Source patterns synthesized:
- `docs/LESSONS_AND_HANDOFF_LOOP.md`: candidate lessons and asset-use feedback must be evidence-backed and not silently change scores.
- `docs/CONTEXTUAL_LEARNING_AND_WORKTREE_ARCHAEOLOGY.md`: context-bound lessons must carry applicability limits and danger notes.
- `docs/LOGOS_REUSABLE_ASSET_FINDINGS.md`: governed learning loops use expectation, exception, learning signal, adaptation proposal, human review, and promotion logs.
- Current Phase 2 calibration review: temp fixture schema copies can indicate schema-family value while being over-scored as individual asset instances.
- Current catalog analysis: repeated temp schema copies often share normalized JSON with canonical/source variants; one schema family showed meaningful version evolution.

Implemented deterministic surfaces:
- `registry/learning-rule-registry.json`
- `schemas/learning-rule.schema.json`
- `agent preflight` now surfaces matching reviewed learning rules.
- `agent midflight` blocks on missing acknowledgements for matching reviewed rules with `require_ack` or `human_gate`.

Seed reviewed rules:
- `learning-rule:current-score-before-upside`
- `learning-rule:temp-fixture-copy-is-lineage-evidence`
- `learning-rule:context-bound-lessons-need-non-applicability`

Midflight evidence:
- Session: `dad:session:757f00cd-13d5-43e4-93bf-917030cb17ca`
- Matched all three seed rules for Phase 2 calibration of temp fixture schema copies.
- Acknowledged all required rules before continuing.

Important limits:
- These rules constrain future review behavior; they do not prove any asset score.
- Temp fixture copies should not be deleted or ignored. Version/hash/normalized-diff lineage may be valuable family-level evidence.
- A copied fixture can still be valuable if reviewed evidence proves unique content or an intentional fixture-coverage role.
