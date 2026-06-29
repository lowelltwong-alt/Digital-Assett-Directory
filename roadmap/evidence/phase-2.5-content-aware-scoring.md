# Phase 2.5 Content-Aware Scoring Recommendation

Status: completed candidate score-methodology validation for the Phase 2
reviewed code/workflow defect set. Scores remain generated heuristics, not
source-repository truth or calibrated probabilities.

Date: 2026-06-26

## Recommendation

Adopt `asset-value-v0.3-content-aware` as the next scoring methodology, then
regenerate the local catalog and re-evaluate it against the 100 reviewed Phase 2
labels before using scores for downstream pilot selection, scheduled alerts, or
proposal generation.

Do not move directly from Phase 2 labels to Phase 3 governance installs on the
old content-blind score. The reviewed evidence showed a stable enough defect
pattern to justify a code fix first.

## Why

Phase 2 reviewed 100 clean calibration records:

- `about_right`: 54
- `too_high`: 18
- `too_low`: 28

The recurring problem was not random label noise. It was structural:

- medium workflow scores were too high when short templates, archive/pinned
  workflow copies, ownership metadata, or thin wrappers received value from
  freshness, provenance, and type labels without enough direct content evidence;
- substantive source code modules were too low when the catalog stored only
  metadata and failed to use readable code structure, module role, imports, and
  public API surface.

The recommended fix is to give the scorer cheap deterministic content shape
without expanding authority. The scanner now records bounded content profiles
for text/code/workflow assets, including skipped oversize readable files. The
scorer can use those profiles for review routing while preserving source files
as authoritative.

## Implemented Slice

- Added deterministic content profiles with line counts, non-empty lines,
  import counts, function/class/public symbol counts, code role, and workflow
  subtype.
- Added profile-only extraction for readable skipped or oversize files, bounded
  at 64 KiB and without full-byte hashing.
- Added `content_profiled` as a content class when bounded profile evidence
  exists without an exact `content_sha256`.
- Added `content_role` as a score component.
- Updated weights to reduce freshness/provenance lift and increase direct
  information content.
- Added discounts for package markers, issue/pull-request templates, ownership
  metadata, archive/pinned workflow copies, and workflow config wrappers.
- Added calibration tuning after churn review so source ruleset/config workflow
  artifacts remain medium review candidates, while small support modules and
  small test helpers stay low without usage evidence.
- Added scoped skipped-file profiling: code, workflow, schema, test,
  configuration, agent, skill, prompt, and evaluation assets receive bounded
  profiles when full content is skipped; low-signal skipped documents remain
  metadata-only for scan performance and authority reasons.
- Added repeatable validation command:
  `python -m digital_asset_directory.cli recommend phase25-score-delta`.
- Preserved `candidate_only` methodology metadata and `heuristic_strength`
  language.

## Acceptance Checks Added

- Substantive source code with a content profile scores materially higher than
  the same metadata-only code observation.
- Issue and pull-request templates score below executable validation workflows.
- Package markers cannot inflate into runtime-code value.
- Oversize/skipped readable code receives a bounded content profile without an
  exact `content_sha256`.

## Read-Only Comparison Against Phase 2 Labels

This initial comparison is historical evidence from before the final churn tune.
It identified the exact overcorrection that the final Phase 2.5 pass fixed.

Codex ran a read-only bounded comparison against the 100 reviewed Phase 2 rows.
This did not rewrite the catalog or commit generated outputs. It reused the
review records, resolved their `git-projects/` paths locally, read at most 64
KiB per file, built v0.3 content profiles, and rescored only in memory.

Aggregate result:

- records compared: 100
- locally resolvable paths: 100
- metadata-only rows upgraded to `content_profiled`: 100
- old band counts: `low=50`, `medium=50`
- v0.3 band counts: `low=29`, `medium=71`
- reviewed `too_high`: 18 of 18 moved down from `medium` to `low`
- reviewed `too_low`: 28 of 28 moved up from `low` to `medium`
- reviewed `about_right`: 39 of 54 stayed in the same band
- reviewed `about_right` churn: 13 moved `low` to `medium`, 2 moved
  `medium` to `low`

Interpretation:

- The targeted false-positive and false-negative patterns moved in the desired
  direction.
- The 15 `about_right` band changes are a real calibration risk. They may be
  acceptable corrections, or they may mean the v0.3 method is overcorrecting.
  A fresh scan and review queue should inspect those rows before downstream use.
- The comparison is not a substitute for a regenerated catalog because it does
  not rebuild duplicate clusters, repository composites, graph edges, or scan
  summaries under v0.3.

## Fresh Scan Validation

Codex then ran fresh local-only v0.3 scans after narrowing skipped-file
profiling to the Phase 2.5 target surfaces and tuning the churn cases.

Final validation command:

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli scan --local-only
python -m digital_asset_directory.cli recommend phase25-score-delta
```

Final scan result:

- scan ID: `dad:scan:cecbf5eb-7d57-4774-b81e-9c37ae0b5a01`
- status: `complete`
- assets: `51241`
- source files mutated: `False`
- changed during scan: `0`
- quarantined non-scoring paths: `57`
- score methodology count: `{'asset-value-v0.3-content-aware': 51241}`

Final score-delta validation:

- validation methodology: `phase-2.5-score-delta-validation-v1`
- generated report: `processed/reports/phase_2_5_score_delta_validation.md`
- status: `passed`
- reviewed rows matched: `100 / 100`
- rating counts: `{'about_right': 54, 'too_high': 18, 'too_low': 28}`
- movement by rating:
  `{'about_right': {'low->low': 22, 'medium->medium': 32}, 'too_high': {'medium->low': 18}, 'too_low': {'low->medium': 28}}`
- desired band movement counts:
  `{'about_right': 54, 'too_high': 18, 'too_low': 28}`
- about-right churn count: `0`

Target surface coverage:

- `code`: `1389/1434` content-profiled; metadata-only `0`
- `workflow`: `342/354` content-profiled; metadata-only `12`
- `schema`: `1303/1303` content-profiled; metadata-only `0`
- `test`: `523/524` content-profiled; metadata-only `1`
- `configuration`: `30/30` content-profiled; metadata-only `0`

The broader catalog remains document-heavy and intentionally has many
metadata-only document observations under `max_file_bytes=0`. This is not a
Phase 2.5 blocker because the reviewed defect set and target operational
surface are code/workflow/schema/test/config scoring, not full document
understanding. Future document calibration needs a separate media/document
extraction phase.

## Red-Team And Premortem

This is a necessary fix, not a final calibration answer.

Main failure modes to watch:

- Bounded profiles can still miss meaning. A file can be long and structured but
  wrong, obsolete, duplicated, or unused.
- Line and symbol counts can be gamed by verbose code. They should route review,
  not prove value.
- Python gets stronger deterministic parsing than other languages in this slice.
  Rust, TypeScript, shell, and YAML rely more on regex and path-role signals.
- Workflow subtype detection is heuristic and path-sensitive. A validation
  workflow with unusual names can be under-scored; a template with validation
  words can still need review.
- The Phase 2 labels came from a clean but local sample. They do not prove
  performance on a broad scan, GitHub scan, or future source mix.
- Profile-only extraction reads bounded text from files that were skipped for
  full hashing. This is intentional, but it means the profile is not an exact
  content identity.
- Freshness and provenance were reduced, but not removed. False positives can
  still appear when direct evidence is sparse.
- Generated profiles and scores must not become roadmap truth by themselves.

Stop conditions for this Phase 2.5 pass:

- regenerated target surfaces remain mostly `metadata_only`;
- score changes improve false negatives but create a new wrapper/template false
  positive flood;
- broad scan performance regresses or mutates source repositories;
- validation cannot explain why an asset moved score bands.

All four stop conditions are cleared for the reviewed Phase 2.5 target set.

## Completion Result

Phase 2.5 is complete as a candidate deterministic score-methodology checkpoint.
It is now reasonable to use v0.3 scores as one input to Phase 3 pilot selection,
provided downstream pilot selection still inspects evidence, preserves source
authority, and does not treat scores alone as promotion authority.

Recommended next phase: Phase 3 downstream-governance pilot selection in
warning-only/read-only mode.

## Research Basis

- `roadmap/evidence/phase-2-calibration-human-review-research.md`
- `roadmap/evidence/phase-2-asset-calibration.md`
- `roadmap/evidence/phase-2-calibration-label-table.csv`
- `docs/ASSET_VALUE_MODEL.md`
- Targeted code inspection of scanner, extractor, instance-class, and scoring
  behavior on 2026-06-26.
