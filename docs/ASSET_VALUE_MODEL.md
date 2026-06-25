# Asset Value Model

## Definition of a good digital asset

A high-value asset is not merely large or recent. It tends to be:

- reusable across multiple future tasks;
- verified by tests, examples, or review;
- grounded in clear provenance and source identity;
- composable through schemas, APIs, CLIs, interfaces, or repeatable instructions;
- capable of shortening a future build or preventing a repeated failure;
- understandable by a new human or AI with limited context;
- legally and operationally reusable within its license, sensitivity, and authority boundaries;
- connected to outcomes, dependencies, missing parts, and activation conditions.

The Asset Identity And Similarity Ladder in
`docs/ASSET_IDENTITY_AND_SIMILARITY_LADDER.md` controls how the directory recognizes and
compares assets before scoring them. Hashes can prove exact identity; chunk hashes,
extracted text, graph edges, and later gated embeddings make assets discoverable. None of
those signals alone proves value, authority, or canonical status.

## Highest-compounding asset families

The seed prioritizes these families because they accelerate multiple downstream builds:

1. Evaluation harnesses, golden cases, and regression tests.
2. Source-of-truth, identity, provenance, and version registries.
3. Schemas, ontologies, taxonomies, and data dictionaries.
4. Reusable workflows, agent skills, adapters, and orchestration patterns.
5. Tested code modules, CLIs, APIs, and integration contracts.
6. Failure-mode, edge-case, red-team, and escalation libraries.
7. Lessons learned, postmortems, decision records, and handoffs.
8. Retrieval/ingestion patterns and context-pack builders.
9. Access, entitlement, privacy, confidentiality, and risk controls.
10. Architecture maps, AI front doors, validation commands, and deterministic roadmaps.

High-leverage composite assets often outrank isolated files. Examples include:

- complete AI workflows made from agents, skills, prompts, memory, tools, governance, and evaluations;
- asset bundles that combine schema, extractor, tests, docs, and review workflow;
- repository-level systems where several files only become powerful together;
- model/algorithm packages with code, data, assumptions, calibration, and backtests;
- forecasting systems, scenario trees, simulators, and strategic signal dashboards;
- frontier math or research discovery packs with provenance, proof notes, examples, and evaluator cases;
- adapter/connectors that join otherwise isolated repos, APIs, or knowledge stores;
- cluster-delta assets that compare variants and preserve the best parts of each.

Scoring should surface these patterns as high-upside candidates, but current score still
depends on evidence. A composite candidate needs member assets, pattern evidence, usage or
validation records, and clear authority boundaries before it should be treated as reviewed.

## Score dimensions

```text
asset_value =
  reuse_potential
+ verification
+ provenance
+ composability
+ learning_loop_value
+ uniqueness
+ demand_signal
+ freshness
- bounded_risk_penalties
```

Each dimension is normalized and the resulting 0–100 score is a triage heuristic. It must expose component scores and confidence.

Risk adjustments are applied as a multiplicative factor after the weighted component score. This
keeps risk interpretable as a discount on otherwise useful evidence. Freshness is represented by
the freshness component only, not a second stale penalty. Unknown GitHub repository license status
is a risk factor when GitHub scanning is explicitly enabled and reviewed.

Any calculated score or grade must cite an explicit methodology before it is used for review,
ranking, roadmap evidence, or graph edges. At minimum, the artifact must state:

- methodology version;
- input fields;
- normalization;
- weights or thresholds;
- risk factors;
- uncertainty handling;
- output range;
- whether the value is heuristic, calibrated probability, percentile, or reviewed truth.

If the formula is missing, future agents must treat the value as an uncalibrated heuristic and
should not promote it into source-of-truth, labels, or roadmap completion evidence.

## Dormant option value

Low current use does not mean low future value. The radar preserves:

- capabilities;
- missing dependencies;
- trigger terms;
- likely future outcomes;
- why the asset is dormant;
- what state change could make it important.

This creates an explicit option-value record rather than deleting or forgetting the asset.

## Multi-layer calibration lens

Human calibration should review an asset as a graph node with up to three layers:

1. Grounded current role: what the asset clearly does now, backed by direct code, schema,
   test, or document evidence.
2. Latent role: a smaller signal inside the asset that could become valuable when paired
   with labels, examples, validators, adapters, or another asset.
3. Bridge role: how the asset may connect, upgrade, validate, constrain, or de-duplicate
   other assets for future agents.

Use evidence levels to prevent projected value from being mistaken for current truth:

| Evidence level | Meaning | Score use |
| --- | --- | --- |
| `direct` | Proven by code, schema, test, or explicit source text. | Can support current score. |
| `derived` | Inferred from capabilities, needs, outcomes, path, or nearby tests. | Use lightly and calibrate with human labels. |
| `projected` | Future value if combined with missing work or another asset. | Record as notes, not proof of current score. |

Reviewers should separate floor from ceiling:

- `current_floor` is the generated pre-review current-value band. It may still be
  labeled `too_high`, `about_right`, `too_low`, or `unsure` by a human.
- `current_score_range` is a deterministic uncertainty interval around the generated score.
  The midpoint is the generated score in v1 because the range is symmetric.
- `current_score_uncertainty` records whether that interval is narrow, medium, or wide.
- `potential_ceiling` is conditional upside if activation requirements are satisfied.
- `potential_ceiling_range` expresses uncertainty around that upside. Low-confidence
  projections should use a wider range rather than a crisp ceiling claim.
- `upside_delta` is the number of score bands between generated current floor and potential
  ceiling, so the delta is real and interpretable rather than decorative.
- `upside_delta_range` expresses uncertainty in the band delta.
- `upside_gap` summarizes that delta as `small`, `medium`, or `large`.
- `ceiling_confidence` records how grounded the upside projection is.
- `development_posture` should default to validation when ceiling confidence is low.

Review order matters. Judge the current generated score first using direct and cautiously
derived evidence. Only after choosing the current score label should reviewers inspect ceiling,
delta, and activation conditions for future-development notes. A large delta should tell the
reviewer something concrete: validate the upside, create a bounded experiment, or actively
develop only when confidence and activation evidence support it.

A high ceiling is not a reason to inflate current value. It is a reason to record what would
move the asset toward that ceiling: examples, labels, tests, schemas, adapters, human review,
or graph connections. This is similar to distinguishing a low-floor/high-upside player from a
proven current producer.

The v1 score range is not a statistical confidence interval. It is a calibrated-review
surface based on confidence, verification, and inferred needs. After enough human labels
exist, replace or calibrate it with a measured error model, such as empirical residuals by
asset type and score band.

Actual use is stronger evidence than projected usefulness. When an agent materially uses an
asset, it should run `lesson asset-use` to record how the asset was used, whether it helped,
observed usefulness, observed futurefulness, missing parts, and feedback on the current score
and ceiling range. These records are candidate evidence for future calibration, not automatic
score updates.

Floors and ceilings are review-time projections, not permanent truth. Reevaluate them at
least every six months, and sooner after major source changes, new usage evidence, roadmap
changes, duplicate-cluster discoveries, or new capabilities that alter what the asset can
unlock.

Near-duplicate assets are graph evidence, not trash by default. If two repos reinvented the
same wheel, record whether the relationship is `near_duplicate`, `variant_of`,
`superseded_by`, or `merge_candidate`. Prefer a bounded consolidation proposal over deleting
or double-counting either asset.

For close clusters, create a candidate cluster delta before choosing a default asset. The
delta should separate:

- shared core behavior or knowledge;
- stronger parts in each asset;
- neutral differences that serve different contexts;
- weaker or obsolete parts;
- missing tests, schemas, examples, or adapters that would make comparison fair;
- the smallest merge-or-keep-variant experiment.
