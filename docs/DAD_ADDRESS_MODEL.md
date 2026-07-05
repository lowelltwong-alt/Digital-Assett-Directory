# DAD 9-Layer Address Model

Status: adopted DAD guidance, versioned and expected to evolve.

DAD uses the address model as a coordinate system for assets, lessons,
exceptions, workflows, and learning records. It is not a replacement for the
knowledge graph. Addresses say where a thing belongs and who governs it; graph
edges say how things relate, derive, conflict, compose, or update each other.

## Why This Helps

The model helps when DAD has to move safely across many repos without flattening
local source authority:

- asset cards stay findable without copying private content;
- claims, evidence, validation, and learning outcomes stay separate;
- prior fixes can become lookup triggers instead of chat-only memory;
- workflow and orchestration assets can be represented by compact cards;
- DAD can evolve the system with versioned migration notes instead of breaking
  older records.

It does not help when the record is tiny, one-off, or would become ceremony.
Use the smallest layer set that improves routing, evidence, provenance,
validation, or learning.

## Compact Tuple

The preferred compact address tuple is:

```text
environment / authority_zone / layer / domain / module / object_type / object_id / version
```

For DAD records this usually means:

- `environment`: local, central, public-release, test, or archive context;
- `authority_zone`: source repo, DAD candidate, local adoption, or human release;
- `layer`: one of the 9 layers below;
- `domain`: mail, exceptions lake, coding harnesses, assets, templates, skills,
  governance, data, or architecture references;
- `module`: the specific registry, harness family, workflow family, or repo-local
  surface;
- `object_type`: asset, lesson, harness, schema, mail packet, exception event,
  fix outcome, workflow, template, skill, or trace;
- `object_id`: stable ID;
- `version`: schema version, asset version, hash, or review version.

Do not paste long prose into the address. Use IDs, paths, hashes, tags, and
short summaries, then point to the larger doc, schema, workflow card,
validation report, or learning record.

## Layers

1. `identity`: stable IDs, repo IDs, trace IDs, return addresses.
2. `object`: what the thing is, without its claims.
3. `claim`: usefulness, novelty, risk, and applicability claims.
4. `relationship`: parent, derivative, variant, dependency, and upgrade links.
5. `validation`: tests, evidence, review state, and false-confidence warnings.
6. `retrieval`: context tags, use-when triggers, and preflight routes.
7. `fractal_address`: stable placement across repo-local and DAD surfaces.
8. `artifact_evidence`: source paths, hashes, provenance, and sensitivity.
9. `learning_adaptation`: what changed, what worked, what failed, what should be
   reused, upgraded, retired, or looked up next time.

DAD adopts layer 9 as a real learning/adaptation layer because DAD is a learning
control plane. LawFirm OS also has observed ninth-layer variants for
orchestration/workflow. DAD preserves those as source-repo variants and
workflow tags, but DAD's own ninth layer is `learning_adaptation`.

## Workflow Encoding

Workflows should be compact cards, not pasted narratives.

A workflow card should contain:

```json
{
  "workflow_id": "workflow:example",
  "trigger": "when this should run",
  "owner_authority": "source_repo|dad_candidate|human_release",
  "cadence": "daily|weekly|task-triggered|manual",
  "inputs_ref": "schema or source pointer",
  "outputs_ref": "schema or output pointer",
  "steps": ["step:1", "step:2"],
  "gate_refs": ["gate:privacy", "gate:validation"],
  "failure_modes": ["false_green", "stale_report"],
  "validation_ref": "command or report pointer",
  "learning_ref": "layer-9 record pointer"
}
```

Step cards should stay equally small: `step_id`, verb, input ref, output ref,
tool or command ref, gate ref, and failure-mode ref.

If a workflow needs a full prompt, script, diagram, or policy explanation, keep
that in a separate file and point to it.

## Evolution

The address model is expected to change. Changes should be additive when
possible. Breaking layer or segment changes require:

- a new model version;
- a migration note for existing cards;
- synthetic fixtures showing old and new cards remain readable;
- red-team and premortem review;
- frontier AI/architecture review when the change affects recursive learning,
  workflow cards, or context-pack routing.

Frontier recommendations are candidate-only until DAD has tests, examples, and
a reviewed migration path.

Source authority remains local. The model helps DAD route and learn; it does not
authorize source mutation or prove graph truth.
