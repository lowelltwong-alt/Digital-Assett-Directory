# Algorithm Calibration Not Ready - 2026-06-24

## Scope

This evidence records the calibration state after implementing deterministic algorithm fixes from
`docs/ALGORITHM_CALIBRATION_AND_FIXES_HANDOFF.md`.

## Implemented Before Calibration

- `related_to` similarity changed from unweighted Jaccard to IDF-weighted cosine.
- Candidate related-edge token selection now uses the rarest bounded tokens.
- Context-pack ranking now uses IDF-weighted cosine.
- Near-duplicate detection changed from fixed-window prefix chunks to overlapping token shingles and deterministic MinHash.
- Containment candidates are emitted as `contained_in` edges when exact shingle containment is high but symmetric similarity is lower.
- Synergy scoring excludes exact/near duplicate pairs and scores complementarity-given-proximity instead of sameness.
- Scoring risk penalties are multiplicative; unknown GitHub license is wired; stale freshness is not double-counted.
- Scan summaries include `changed_during_scan_count`.

## Label Availability

Calibration was attempted against the available generated review files:

- `processed/proposals/proposal_review_template.jsonl`: 50 rows, 0 reviewed, 50 pending.
- `processed/calibration/asset_rating_template.jsonl`: 50 rows, 0 reviewed, 50 unreviewed.

Because no human labels are present, precision, recall, ROC/PR curves, Platt/logistic calibration,
and weight fitting are not statistically meaningful. No candidate was promoted and no confidence
field was treated as a probability.

## Threshold State

The following thresholds remain deterministic defaults pending human labels:

| Parameter | Current value | Calibration status |
|---|---:|---|
| `related_similarity_threshold` | `0.34` | not calibrated; no reviewed labels |
| near-duplicate MinHash threshold | `0.50` | not calibrated; no reviewed labels |
| containment threshold | `0.82` | heuristic default; no reviewed labels |
| `synergy_alert_threshold` | `0.64` | not calibrated; no reviewed labels |

## Required Next Human Gate

Before calibration can be completed:

- review at least 50 asset rating records;
- review at least 25 bottom-up and 25 top-down proposal records;
- include false-positive, false-negative, and useful-example notes;
- then rerun calibration and record actual precision/recall and any weight changes.

## Authority

This file is evidence that calibration failed closed. It is not evidence that Phase 2 calibration is
complete, and it does not change roadmap phase status.
