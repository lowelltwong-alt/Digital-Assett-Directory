# Cross-Repo Governance Dependency Map Pattern

Status: implemented as DAD asset-pattern plus template seed.

## Purpose

Turn the Logos cross-repo governance dependency-map pattern into a reusable DAD
digital asset and template seed for future repo families. The reusable asset is
domain-general: an upstream/control-plane repo owns governance truth, child repos
mirror the relevant local controls, and validators make governance-facing drift
fail closed.

## Reference Examples Inspected

- `logos-governance-architecture`: upstream map plus changed-path validator.
- `logos-boundary-literature`: child mirror plus local mirror validator.
- `logos-scripture-graph`: child mirror and validator from `origin/main`.

The examples were read-only references. The DAD template removes domain-specific
source language and uses placeholders for authority, trust zones, and repo names.

## Premortem

- Too Logos-specific: avoided by using generic control-plane and child-repo
  language and by blocking copied domain rules in the adoption guide.
- Incorrect template authority: every template file says scaffolds are not
  authority and must point to the target repo's real source of truth.
- Stale boilerplate: the template includes validator and test stubs and is
  registered in the template dependency registry.
- Stored but undiscoverable: the pattern is surfaced in the asset-pattern
  registry, AI front door, AI TOC, README, template governance docs, and semantic
  recognizer hints.
- Over-collection during scans: the scanner checklist requires signal clusters
  and validator-backed evidence, not single-word matches.
- Accidental AI authorization: the docs state that generated scaffolds, DAD
  records, and templates cannot authorize governance or child-repo overrides.

## Red-Team Findings

- A new repo could be created without a governance map if only prose is copied.
  Fix: adoption checklist requires the map, discovery sections, validator, and
  test before completion.
- A child repo could change governance-facing files without updating mirrors.
  Fix: mirror template contains watched local governance surfaces and
  fail-closed required behavior.
- Local repos might appear to override upstream governance.
  Fix: map and mirror authority fields force non-override values.
- Templates could include text but no validation.
  Fix: template seed includes validator and test stubs; DAD tests assert those
  files exist and contain fail-closed checks.
- Repo scanning could over-match generic governance files.
  Fix: semantic recognition requires multiple evidence signals and docs require
  signal clusters.

## Acceptance

- Asset pattern added: `cross_repo_governance_dependency_map_pattern`.
- Template registered: `template:cross-repo-governance-dependency-map`.
- Template module added under `templates/cross-repo-governance-dependency-map/`.
- Adoption guide and scanning checklist added.
- AI discovery surfaces updated.
- Tests added for registry, template, and semantic recognition.

## Validation

Validation results should be recorded in the postflight for the implementation
session. The required baseline is:

```powershell
python -m pytest
python -m ruff check src tests scripts noxfile.py
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli validate
$env:PYTHONPATH='src'; python -m digital_asset_directory.cli roadmap check --no-update
```

## Remaining Risks

- The template is a seed. It still needs human adaptation for each repo family.
- Validator stubs are intentionally minimal; adopting repos must fill in their
  real watched paths, companion surfaces, and changed-path logic.
- DAD can detect candidates, but human review must decide whether a repo truly
  needs this pattern.

