# Architecture Consult

Status: generated-candidate advisor for seeding new repositories from DAD's
local catalog.

Architecture Consult V1 lets a repo-seeding chat or coding agent ask DAD what
known architecture patterns, templates, workflow parts, gates, and learning
loops should shape a new repo before implementation starts.

The command is consult-and-compose, not copy-and-impose. DAD advises a seed
architecture pack from local generated evidence. The new repository keeps its
own canon, source-of-truth, and design authority.

Persistent repos should include a lightweight DAD mailbox by default:
`.digital-asset/mail/README.md` plus append-only inbox/outbox/archive JSONL
files. Mail is candidate suggestion transport only; it does not install
governance or adopt cross-repo lessons without local review.

## Command

```powershell
$env:PYTHONPATH='src'
python -m digital_asset_directory.cli recommend architecture-consult --intent-file "<new-repo-intent.md>" --limit 10
```

The command writes:

```text
processed/reports/architecture_consults/<slug>.md
processed/reports/architecture_consults/<slug>.json
processed/reports/architecture_consults/<slug>_seed_prompt.md
```

All outputs are generated candidates. They must not be committed as truth,
installed into a target repo automatically, or used to mark a roadmap phase
complete.

## Intent File

The intent file is a small human-readable brief:

```text
Purpose: Seed a governed AI workflow repo.
Domain: AI software governance
Risk level: high
Data sensitivity: internal
Expected users/agents: Codex, Claude, human maintainer
Workflows needed: AI navigation, schema contracts, validation, learning loop
Validation needs: pytest, schema validation, privacy review
```

The parser accepts common label variants, normalizes risk and data sensitivity,
and redacts secret-like text before any output is written. If redaction happens,
the privacy gate fails and the consult includes a warning.

## Inputs

Architecture Consult reads existing local artifacts only:

- `processed/learning/reference_architecture_candidates.jsonl`
- `processed/reports/reference_architectures.json`
- `registry/template-registry.json`
- `processed/workflow_parts/workflow_part_usage_guidance.json`
- `processed/learning/background_connection_candidates.jsonl`
- `processed/reports/governance_map_adoption_scope.json`
- `registry/learning-rule-registry.json`
- `docs/SOFTWARE_REPO_CHECKLIST_TREE.md`

It does not rescan, read source repo contents, call GitHub, call models, mutate
source repositories, install hooks, promote candidates, or refresh upstream
reports.

## Output Semantics

The consult returns:

- best matching reference architectures and why they apply;
- parts and roles to reuse from those architectures;
- what not to copy;
- a unique architecture combination plan;
- a starter repo structure;
- template dependencies and validation commands;
- DAD mail inbox/outbox guidance for persistent repos;
- workflow-part, learning-rule, governance, and background-connection cues;
- required human gates;
- a seed prompt for a future coding agent.

The seed prompt is deliberately bounded. It tells the new repo agent to reuse
architecture shapes and dependency order, not source-owned facts.

## Scoring

The V1 match formula is:

```text
match_score =
  100 * (
    0.45 * source_strength
  + 0.35 * intent_overlap
  + 0.20 * context_boost
  )
```

`source_strength` comes from the existing reference-architecture score.
`intent_overlap` is deterministic token overlap between the intent and
candidate metadata. `context_boost` rewards matches such as high-risk intents
with governance roles, non-public data with public-safe boundaries, validation
needs with schema/test roles, and learning-loop needs with learning-loop roles.

The score is a ranking signal for human review. It is not proof of correctness,
value, authority, or permission to copy.

## Human Gates

At minimum, every consult requires human review before it becomes repo canon.
Additional gates are added for:

- high-risk repos;
- internal or restricted data;
- cross-repo governance maps, mirrors, validators, hooks, or managed blocks;
- any source-owned example, fact, or domain rule that might be copied.

## Failure Modes

- Generated candidate evidence can be stale or missing.
- File names and metadata can overstate what a system actually does.
- Cross-repo inspiration can accidentally transfer authority.
- A seed prompt can be mistaken for an implementation plan.
- Template dependencies can be copied without adapting validation and gates.

When in doubt, treat the consult as a shopping list for review, not as a build
order.
