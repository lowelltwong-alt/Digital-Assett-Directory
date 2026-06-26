# Background Connection Radar V1 Implementation Evidence

Status: implemented and validated as a manual generated-candidate workflow.

Implementation date: 2026-06-26

## Scope

Implemented a local-only, manual Background Connection Radar v1.

The v1 command is:

```powershell
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli recommend background-connections --attention recent --cold older --limit 50 --escalation-budget 5 --tau 0.70 --max-hops 2 --reserve-cold 2
```

It reads the existing catalog database and generated graph outputs only. It does
not rescan local sources, call GitHub, call external models, run as a daemon, or
mutate scanned source repositories.

Generated outputs are ignored candidate evidence:

- `processed/learning/background_attention_seeds.jsonl`
- `processed/learning/background_connection_candidates.jsonl`
- `processed/learning/background_escalation_packets.jsonl`
- `processed/learning/background_expansion_maps.jsonl`
- `processed/reports/background_connection_candidates.md`
- `processed/reports/background_connection_escalation_packets.md`

## Contracts

New registered candidate contracts:

- `AttentionSeedRecord`
- `ConnectionCandidateRecord`
- `EscalationPacketRecord`
- `ExpansionMapRecord`

All four include methodology version, provenance/evidence, scan ID,
generated timestamp, and `review_status="generated_candidate"`.

`AttentionSeedRecord` enforces `raw_text_persisted=false`.
`EscalationPacketRecord` enforces `safety_cleared=true`; unsafe candidates are
blocked before packet creation.

## Methodology

Methodology version: `background-connection-connectivity-v1`

Escalation uses gate-before-score:

- `safety_gate`
- `evidence_gate`
- `authority_gate`

A failed gate forces `escalation_eligible=false`, even when the numeric
connectivity score is high.

The score is:

```text
connectivity_score =
  0.30 * attention_relevance
+ 0.20 * cold_lift
+ 0.25 * complementarity
+ 0.15 * multi_hop_potential
+ 0.10 * novelty
```

Hard caps:

- hot attention seeds: `200`
- per-seed neighbors: `50`
- escalation packets: configured by `--escalation-budget`, default `5`
- cold reserve: configured by `--reserve-cold`, default `2`
- max hops: `2`
- max expansion nodes: `25`

Family dedup runs before budget allocation. Candidate families are keyed by
connection type and endpoint family keys; duplicate and variant edge families
share one family key, including the root member of the family.

## Red-Team

Privacy leak risk:

- Attention seeds are derived from repo/catalog artifacts, not raw chat.
- `raw_text_persisted=false` is enforced by both model and schema.
- Escalation packets include bounded minimal context and redacted snippets.

Repeated-family budget capture:

- Variant/duplicate families are unioned before packet selection.
- Root and non-root duplicate-family members share the same family key.
- Deduped candidate IDs are attached to the representative packet.

Stale scan or edge use:

- Existing pair-edge evidence must match the current scan ID.
- Stale edge evidence fails the evidence gate.

Duplicate similarity mistaken for complementarity:

- Exact, near-duplicate, variant, noise, containment, and delta-family edge
  types apply a duplicate-similarity penalty.
- Existing pair edges zero novelty.

Cross-authority unsafe composition:

- Cross-source source-owned candidates are labeled `requires_human_gate`.
- They fail `authority_gate` and cannot become escalation packets in v1.

Compute blowup:

- The scout uses indexed per-seed candidate pools instead of all-pairs search.
- Expansion maps stop at two hops and twenty-five nodes.

Generated candidate leakage into current score:

- Records are written only under ignored `processed/` generated-output paths.
- The implementation does not update asset value scores, graph truth, roadmap
  phase status, or source files.

## Premortem

Failure mode: recent attention overfits to whatever changed last.
Mitigation: reserve cold slots and report cold cues explicitly.

Failure mode: repeated fixture or duplicate families consume all review budget.
Mitigation: family dedup before packet selection.

Failure mode: lexical overlap creates false connections.
Mitigation: evidence gate requires multiple signal families, and packets require
human or future verifier review.

Failure mode: cross-domain or cross-authority composition suggests unsafe reuse.
Mitigation: authority gate blocks escalation and records the human-gate need.

Failure mode: future agents treat v1 packets as proof.
Mitigation: every contract defaults to generated candidate status and TOC rows
label outputs as generated evidence, not source truth.

## Validation

Focused validation:

```text
python -m pytest tests\test_background_connections.py tests\test_schema_conformance.py
```

Result: `16 passed`

Required validation:

```text
python -m pytest
python -m ruff check src tests scripts noxfile.py
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli validate
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli roadmap check --no-update
```

Results:

- `python -m pytest`: `163 passed in 22.00s`
- `python -m ruff check src tests scripts noxfile.py`: `All checks passed!`
- `validate`: valid, `checked_count=65`, `errors=[]`
- `roadmap check --no-update`: passed; no roadmap phase status was edited

Environment warning:

- On this Windows/Python 3.12 environment, pytest printed a non-failing
  `Windows fatal exception: access violation` trace after reporting all tests
  passed. The command exit code was `0`. The trace appeared in imports from
  third-party libraries (`jsonschema`/`attrs` in focused tests and
  `requests`/`charset_normalizer` in full tests), not in the new radar module.

## Real-Catalog Smoke Run

Command:

```powershell
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; python -m digital_asset_directory.cli recommend background-connections --attention recent --cold older --limit 50 --escalation-budget 5 --tau 0.70 --max-hops 2 --reserve-cold 2
```

Result:

- `attention_seed_count`: `200`
- `candidate_count`: `10000`
- `eligible_candidate_count`: `0`
- `packet_count`: `0`
- `expansion_map_count`: `0`
- `gate_failures`: safety `1785`, evidence `9979`, authority `0`
- Runtime on current catalog of roughly 95k assets / 654k edges: about 130s

Interpretation:

- The current catalog produced many generated candidates, but none met
  `tau=0.70`; no escalation packets were created.
- Some candidates passed all gates but remained below threshold. This is a
  conservative v1 outcome and should be calibrated later rather than forced by
  lowering gates during implementation.
- The generated files remain under ignored `processed/` paths.

## Acceptance Status

Accepted for manual v1 use only.

Not accepted as:

- autonomous daemon behavior;
- model-verified truth;
- roadmap phase completion evidence;
- current value-score evidence;
- source-repository authority.
