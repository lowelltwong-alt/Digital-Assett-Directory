# Cross-Repo Governance Dependency Map Pattern

Status: reusable DAD digital asset and template seed.

This pattern captures a repo-family governance workflow where one upstream or
control-plane repo owns governance truth and child repos carry local mirrors,
front-door routing, and validators. The pattern is portable across domains. A
template generated from it must point to the target repo family's actual
authority and must never imply that DAD, the template, or a child repo can
override upstream governance.

Seed examples inspected read-only:

- `logos-governance-architecture` governance dependency map and validator.
- `logos-boundary-literature` local governance dependency-map mirror and
  validator.
- `logos-scripture-graph` local governance dependency-map mirror on
  `origin/main`.

These examples supplied the architecture shape only. Domain-specific rules,
labels, theological language, and source-specific authority claims are not part
of the reusable template.

## Reusable Shape

```text
upstream governance authority
-> machine-readable governance dependency map
-> child repo mirror controls
-> AI front door and TOC discovery surfaces
-> repo contract and PR-description requirements
-> fail-closed validator and test
-> handoff/adoption checklist
```

The control-plane map records:

- governance-facing files and directories;
- companion surfaces that must be reviewed when governance changes;
- child mirror surfaces;
- validators and tests;
- authority rules, including non-override rules;
- evidence that the map itself is governed.

The child mirror records:

- upstream map repo, path, artifact/rule id, and source-of-truth status;
- local mirror file, validator, test, front door, TOC, README, and repo contract;
- watched local governance surfaces;
- non-override and fail-closed behavior.

## When To Use It

Use this pattern when:

- multiple repos form one system or repo family;
- one repo owns governance, contracts, schemas, routes, or policy for others;
- child repos need local reminders and local fail-closed checks;
- AI agents might otherwise rely on chat memory, stale boilerplate, or copied
  fragments;
- PR descriptions need to disclose governance-facing changes.

Do not use it when:

- the repo is a short-lived scratch repo with no downstream consumers;
- there is no upstream/local authority relationship;
- the team cannot maintain validators;
- the template would copy a domain rule instead of adapting authority language.

Danger if misapplied:

- A child repo can appear to have authority it does not have.
- Boilerplate can go stale and create false confidence.
- Governance prose can be stored but never surfaced to AI agents.
- Validators can over-collect random docs instead of checking the actual
  governance surfaces.

## Template Seed

The reusable template module is:

```text
templates/cross-repo-governance-dependency-map/
```

It includes:

- `GOVERNANCE_DEPENDENCY_MAP.yaml`
- `governance_dependency_map_mirror.yaml`
- `AI_FRONT_DOOR.section.md`
- `AI_TABLE_OF_CONTENTS.section.md`
- `repo-contract.section.md`
- `PR_DESCRIPTION_REQUIRED_SECTIONS.md`
- `validate_governance_dependency_map.stub.py`
- `test_governance_dependency_map.stub.py`
- `HANDOFF_CHECKLIST.md`
- `ADOPTION_CHECKLIST.md`

New repos should copy only the files and sections that fit their actual
authority model, then replace placeholders with repo-specific names, paths,
trust zones, and validation commands.

## What Not To Copy From Seed Examples

Do not copy:

- domain-specific authority language;
- source-specific artifact ids;
- repo names, owner names, or paths;
- data rules unrelated to the new repo's sources;
- child-repo non-overrides that reference the wrong upstream;
- validator phrase checks that prove only copied boilerplate.

Do copy and adapt:

- the non-override posture;
- explicit source-of-truth fields;
- watched governance path gates;
- companion surface review requirements;
- front-door and TOC discovery rows;
- PR-description governance disclosure;
- validator and test structure.

## Repo-Scanning Checklist

When scanning existing repos for this pattern or missing versions of it, look
for signal clusters rather than single words:

- repeated governance workflows across a repo family;
- a control-plane or upstream repo plus child/consumer repos;
- AI front doors, AI TOCs, repo contracts, or machine navigation manifests;
- governance dependency maps, data-flow maps, route maps, or authority maps;
- child mirror files under `.ai/`, `config/governance/`, `governance/`, or
  similar local-control folders;
- validator-backed governance rules, not only prose;
- tests that make missing mirrors or stale discovery surfaces fail closed;
- PR-description sections requiring governance map/mirror review;
- premortem, red-team, fix-loop, and handoff checklists;
- explicit statements that generated outputs, templates, or child repos cannot
  override source authority.

Treat a repo as missing the pattern when:

- governance-facing files exist but no map names dependencies;
- child repos mention upstream authority but have no local mirror validator;
- front doors route agents to governance docs but no validator checks drift;
- PRs can change governance-facing files without declaring map/mirror impact;
- boilerplate mentions another domain or repo family without adaptation.

## Validation

Minimum validation for an adopted repo:

```powershell
python scripts/validate_governance_dependency_map.py
python -m pytest tests/test_governance_dependency_map.py
```

If a child mirror is used:

```powershell
python scripts/validate_governance_dependency_map_mirror.py
python -m pytest tests/test_governance_dependency_map_mirror.py
```

Each repo should also include the map or mirror validator in its normal
validation suite or CI. A template without validation is only a note, not this
pattern.

