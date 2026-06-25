# Phase 2 Claude Second Opinion Intake

Status: open intake area for Claude Code or another reviewer. Findings here are
independent recommendations only until the human approves labels or evidence.

## Where Claude Should Write

Add a new dated section under `## Findings Log` in this file.

Do not edit generated review files, apply calibration labels, update
`roadmap/gate-evidence.json`, or mark a roadmap phase complete unless the human
explicitly asks for that action.

## Review Scope

Review the pending first-batch Phase 2 asset calibration examples from:

- `asset-review-002`
- `asset-review-003`
- `asset-review-005`
- `asset-review-007`
- `asset-review-008`
- `asset-review-009`
- `asset-review-010`
- `asset-review-011`
- `asset-review-012`

Primary research note to inspect:

- `roadmap/evidence/phase-2-temp-fixture-calibration-research.md`

Methodology files to inspect before recommending labels:

- `docs/ASSET_VALUE_MODEL.md`
- `docs/DETERMINISTIC_LEARNING_RULES.md`
- `docs/SEMANTIC_EVOLUTION_GRADING.md`
- `roadmap/evidence/semantic-evolution-grading.md`
- `processed/calibration/asset_rating_template.jsonl`
- `processed/reports/semantic_evolution_candidates.md`
- `processed/learning/semantic_evolution_candidates.jsonl`

## Required Scoring Lens

Use the same scoring logic as DAD so the second opinion is apples-to-apples:

1. Judge current score first.
2. Separate copied-instance value from schema-family value.
3. Classify path authority before relying on path semantics.
4. Check exact duplicates, near duplicates, same-basename counts, and normalized
   schema deltas.
5. Use upside/ceiling only after the current-score recommendation.
6. Keep all recommendations candidate-only.

## Suggested Research Layers

Claude may add an extra research layer if it improves decision quality. Useful
layers include:

- local test intent: what runtime test caused the copied contract repo to exist;
- canonical/source comparison: whether source variants contain the same schema;
- semantic-evolution comparison: whether the family has real structural change;
- external design context: whether the schema type has architectural importance
  beyond this repo, stated as general context rather than proof of local value;
- failure-mode analysis: what would go wrong if the copied instance were scored
  too high or too low.

## Findings Format

Use this table when possible:

| sample_id | recommended label | agree with Codex? | evidence read | fixture vs canonical conclusion | extra research layer | score/weight suggestion | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `asset-review-002` | `too_high/about_right/too_low/unsure` | `yes/no/partial` | paths, commands, reports | copied instance vs family value | what was added | scoring fix or none | `low/medium/high` |

Then add short notes:

- False-positive risk:
- False-negative risk:
- Useful family-level evidence:
- Danger if this lesson is applied outside temp fixture copies:

## Findings Log

### 2026-06-25 - Claude Code Read-Only Second Opinion

Source: user-provided Claude transcript in local Codex attachment
`C:\Users\lowel\.codex\attachments\7bf83181-ae9f-41b5-9cf6-48a421bc51cc\pasted-text.txt`.

Scope covered:

- `asset-review-002`
- `asset-review-003`
- `asset-review-005`
- `asset-review-007`
- `asset-review-008`
- `asset-review-009`
- `asset-review-010`
- `asset-review-011`
- `asset-review-012`

Claude did not review `asset-review-004` or `asset-review-006` in this
transcript. That was expected because this pass covered the remaining first-batch
records already identified as temp fixture schema copies.

#### Method Used

Claude's method was read-only and independent. It did not edit files or apply
labels. The transcript reports that Claude:

1. Read the requested methodology files.
2. Read `processed/calibration/asset_rating_template.jsonl`.
3. Extracted only the nine target review records and their key scoring fields.
4. Checked semantic-evolution records for the target basenames.
5. Streamed the large catalog by basename to count canonical/source variants
   versus temp fixture variants.
6. Compared the score drivers against the DAD scoring model.

Method differences from Codex's earlier research:

- Claude focused more directly on the scoring components in the review template.
- Claude explicitly identified that the nine records share an identical generated
  score of `66.75` and identical stale `uniqueness=55.0` components from the
  pre-fix calibration template.
- Claude quantified the temp-to-canonical copy flood per basename.
- Claude concluded that the duplicate-awareness fix would barely move these
  scores because uniqueness has too little weight to discipline copied fixture
  floods.
- Claude framed the root cause as score routing: value belongs to canonical
  schema families and harnesses, not the copied fixture instances.

#### Verdict Table

| sample_id | recommended label | agree with Codex? | evidence read | fixture vs canonical conclusion | extra research layer | score/weight suggestion | confidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `asset-review-002` | `too_high` | yes | review template, semantic-evolution records, catalog counts | temp fixture copy; canonical/schema-family value is real | only target with recorded family semantic evolution: `0.9`, `mixed_signal`, two semantic versions | route value to canonical family; copied instance should not receive medium current score | high |
| `asset-review-003` | `too_high` | yes | review template, catalog counts | temp fixture copy of canonical `frontier-review-record.schema.json` family | evaluation/review harness value belongs to canonical/harness layer | copied instance should be lineage evidence | high |
| `asset-review-005` | `too_high` | yes | review template, catalog counts | same fixture family as `asset-review-003` | event-listing test reuse evidence | copied instance should be lineage evidence | high |
| `asset-review-007` | `too_high` | yes | review template, catalog counts | temp fixture copy of canonical `span-selector.schema.json` family | grounding/schema family value belongs to canonical layer | copied instance should be lineage evidence | high |
| `asset-review-008` | `too_high` | yes | review template, catalog counts | temp fixture copy of canonical `evaluation-run.schema.json` family | evaluation harness value belongs to canonical/harness layer | copied instance should be lineage evidence | high |
| `asset-review-009` | `too_high` | yes | review template, catalog counts | temp fixture copy of canonical `embedding-set.schema.json` family | retrieval/embedding family value belongs to canonical layer | copied instance should be lineage evidence | high |
| `asset-review-010` | `too_high` | yes | review template, catalog counts | temp fixture copy of canonical `skill-gap-detection.schema.json` family | no recorded semantic evolution for this family in reviewed set | copied instance should be lineage evidence; investigate unique deltas separately if needed | high |
| `asset-review-011` | `too_high` | yes | review template, catalog counts | temp fixture copy of canonical `claim_v3.schema.json` family | core contract value belongs to canonical layer | copied instance should be lineage evidence | high |
| `asset-review-012` | `too_high` | yes | review template, catalog counts | temp fixture copy of canonical `legal-document-span-ref.schema.json` family | grounding/span-reference value belongs to canonical layer | copied instance should be lineage evidence | high |

#### Key Findings To Preserve

- All nine reviewed assets are under `.pytest-tmp-root/pytest-of-Lowell/.../contract-repo/schemas/...`.
- All nine were scored `66.75` despite having zero instance-level capabilities,
  needs, or outcomes.
- Claude attributes the `66.75` mostly to schema type bonuses,
  freshness/provenance, and path/type signals.
- The calibration template appears stale for this point because these rows show
  `uniqueness=55.0`, which Claude identified as a pre-fix constant.
- `external_identifier.schema.json` is the one target family with recorded
  semantic-evolution signal. Claude agreed that this is real family-level value,
  not value of the pytest copy.
- The canonical home for these schema families is reported as
  `LawFirm-os-semantic-substrate/schemas/...`.

#### Scoring Fixes Claude Recommended

Claude recommended the following methodology fixes:

- Add path or instance class as a scoring input, not only metadata.
- Exclude or quarantine pytest sandboxes such as `**/.pytest-tmp-root/**` and
  `**/pytest-of-*/**` from independent scoring or calibration sampling.
- Gate schema type bonuses on canonical/source class or corroborating evidence,
  not `asset_type=schema` alone.
- Score the canonical duplicate-cluster representative, not every copied member.
- Suppress or reroute freshness for temp/generated classes so copy recency is
  not rewarded as maintenance freshness.
- Regenerate the calibration template under the current scorer and dedupe or
  cluster before sampling.

#### Context Limits

Applies when:

- an asset review record is a temp/pytest/copied-contract-repo fixture;
- canonical/source variants exist;
- the question is current independent value of the copied instance.

Does not apply when:

- the copied fixture is the only available source of truth;
- the asset being evaluated is the fixture harness or coverage pattern itself;
- a reviewed delta proves a copied fixture contains unique behavior or a better
  canonical candidate.

Danger if misapplied:

- blanket suppression of temp fixtures could erase useful lineage, coverage, and
  semantic-evolution evidence;
- failure to suppress copied-instance scores can flood DAD with false
  medium/high-value assets.

#### Calibration Implication

Claude found no disagreement with Codex's recommendation. The second opinion
strengthens the recommendation to label these nine copied instances `too_high`
if the human approves applying those labels. The value should be preserved on
canonical schema assets, schema-family clusters, harness/workflow assets, and
lineage edges rather than on each temp fixture copy.

### 2026-06-25 - Claude Code All-50 Read-Only Triage

Source: user-provided Claude transcript in local Codex attachment
`C:\Users\lowel\.codex\attachments\bc19a1bc-697c-42e0-8edf-f394396dc9f1\pasted-text.txt`.

Status: read-only triage recommendations only. No labels were applied by Claude
or by this evidence update.

#### Gate Assessment

This triage does not complete Phase 2 calibration by itself.

Current DAD summary at capture time:

- `template_count`: 50
- `reviewed_count`: 3
- `unreviewed`: 47
- `calibration_gate_complete`: false
- `structured_notes_complete`: false
- `false_positive_note_count`: 1
- `false_negative_note_count`: 0
- `weight_change_note_count`: 3

The triage is useful because it covers all 50 records and provides label
recommendations. The Phase 2 gate still requires human-approved labels in
`processed/calibration/asset_rating_template.jsonl` plus the required structured
notes.

#### Claude Coverage Summary

Claude reported:

| coverage | count | sample IDs |
| --- | ---: | --- |
| prior deep-reviewed by Claude | 9 | `002`, `003`, `005`, `007`, `008`, `009`, `010`, `011`, `012` |
| newly triaged | 38 | `013`-`019`, `020`, `021`-`025`, `026`-`050` |
| needs deep review | 3 | `001`, `004`, `006` |

Claude found three distinct generated scores across the 50 records:

- `71.4` x 1
- `66.75` x 24
- `35.25` x 25

Claude found three path classes:

- source: 28
- temp fixture: 21
- worktree: 1

#### All-50 Triage Table

| sample IDs | score | type/class | Claude recommendation | reason |
| --- | ---: | --- | --- | --- |
| `001` | `71.4` | `evaluation` / source | needs deep review; likely `too_high` | `__init__.py` appears mis-typed as evaluation; highest score in set looks like classification/path-match fault. |
| `002`, `003`, `005`, `007`-`012` | `66.75` | schema / temp fixture | `too_high` | Prior deep-reviewed temp copied contract-repo schemas; value belongs to canonical schema/family/harness. |
| `004` | `66.75` | schema / source | needs deep review | `object_set.yaml` appears to be a genuine canonical schema; type bonus may be legitimate. |
| `006` | `66.75` | test / source | needs deep review | Real source test file; decide whether medium score is right for one test based on actual coverage. |
| `013`-`019`, `021`-`025` | `66.75` | schema/evaluation / temp fixture | `too_high` | Additional pytest temp copied schemas or docs behave like the prior nine; no contradiction found. |
| `020` | `66.75` | schema / worktree | `too_high` with caveat | Worktree copy of `vector_index_manifest`; possible active-development caveat, but not independent canonical value without review. |
| `026`, `028`, `037` | `35.25` | media / source | `about_right` to slightly high | Incidental screenshots; near-zero reusable value. |
| `027`, `029`-`036`, `038`-`041`, `043`-`050` | `35.25` | media/research / source | `about_right` current score | Raw, unextracted research PDFs; low current score is defensible, while latent research-family value belongs in ceiling notes. |
| `042` | `35.25` | unknown / source | `too_high` | `.DS_Store` OS junk should be scan-excluded, not treated as a 35-point asset. |

#### Additional Method Signal

Claude's all-50 pass added a corpus-level view:

- The calibration sample is low-discrimination: most records collapse into only
  three scores.
- Content-derived signals are mostly empty, so type, freshness, and provenance
  dominate.
- Media scoring is content-blind: screenshots, `.DS_Store`, and research PDFs
  can receive the same generated score.
- Temp/worktree copies dominate the medium band.
- `.DS_Store`, `.pytest-tmp-root`, and `pytest-of-*` paths should be excluded,
  quarantined, or prevented from independent scoring.

#### Calibration Implication

This should be treated as strong recommendation evidence, not completed
calibration. If the human approves Claude's triage, the next executable step is
to apply labels with reviewer `Lowell`, preserving structured notes:

- false-positive notes for temp fixture copies, `.DS_Store`, and misclassified
  empty/path-only files;
- false-negative notes for low-scored raw research families whose current score
  is low but whose future research-family value may be higher after extraction;
- weight-change notes for path/instance class, type-bonus gating,
  freshness-copy suppression, media extraction, and deduped sampling.

After labels are applied, rerun `recommend calibration-review-summary`. Phase 2
calibration is not past the gate until that summary reports 50 reviewed records
and complete structured notes.
