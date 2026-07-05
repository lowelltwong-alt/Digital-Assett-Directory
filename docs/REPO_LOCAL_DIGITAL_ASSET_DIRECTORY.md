# Repo-Local Digital Asset Directory

DAD uses `.digital-asset/` as the canonical repo-local control surface.

The repo-local digital asset memory lives at:

```text
.digital-asset/assets/README.md
.digital-asset/assets/index.jsonl
.digital-asset/assets/adoption.jsonl
.digital-asset/learning/events.jsonl
```

This is intentionally small. Repos do not need a heavy Python test suite to participate. They need a stable place to remember asset cards and a mailbox to send candidate summaries to DAD.

## Asset Card Rule

`index.jsonl` rows are metadata pointers only. They may contain short summaries, paths, hashes, tags, validation commands, source refs, and review notes. They must not contain secrets, private rows, raw logs, large generated outputs, full source files, hidden reasoning, or source authority copied from another repo.

DAD can collect these rows with:

```text
asset-dir dad repo-assets --repo <repo>
```

The command writes a central candidate report under `processed/reports/repo_local_assets/`. It does not mutate the source repo.

## Fractal Shape

The standard uses a fractal placement model inspired by LawFirm OS substrate research:

1. identity
2. object
3. claim
4. relationship
5. validation
6. retrieval
7. fractal address
8. artifact evidence
9. learning adaptation

DAD adopts layer 9 as `learning_adaptation`: what changed, what worked, what failed, what should be reused, upgraded, retired, or looked up next time. LawFirm OS source material also records `orchestration_workflow` as a ninth-layer variant. DAD keeps that as a source-repo variant and workflow tag, not as DAD's primary layer 9.

Each layer should be filled with compact values or refs. Do not paste long layer explanations into asset cards. If a workflow or orchestration asset needs depth, use a small workflow card with step IDs, input/output refs, gate refs, validation refs, and learning refs.

LawFirm OS remains the source authority for its own address model. DAD stores pointer-only inspiration and does not import the substrate ontology as DAD canon.

See `docs/DAD_ADDRESS_MODEL.md` and `registry/dad-address-model-registry.json` for the adopted model and evolution policy.

## Compatibility

DAD reads the newer `.digital-asset/assets/index.jsonl` first. It can also read compatibility inputs such as:

```text
.digital-asset/dad-ingest/asset_manifest.json
.digital-asset-directory/learning/events.jsonl
```

Those legacy inputs are evidence, not the preferred future shape.
