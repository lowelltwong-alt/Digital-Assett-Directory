## Governance Dependency Map

This repo participates in a cross-repo governance dependency-map pattern.

- Upstream governance authority: `{{UPSTREAM_GOVERNANCE_REPO}}`.
- Upstream map: `{{UPSTREAM_GOVERNANCE_REPO}}/governance/GOVERNANCE_DEPENDENCY_MAP.yaml`.
- Local mirror, if this is a child repo: `.ai/control/governance_dependency_map_mirror.yaml`.
- Local validator: `scripts/validate_governance_dependency_map_mirror.py` or `scripts/validate_governance_dependency_map.py`.

Before editing governance-facing files, agents must check whether the upstream
map, local mirror, this front door, the AI table of contents, repo contract,
README, PR-description sections, validators, and tests also need updates.

This repo must not override, weaken, or reinterpret upstream governance. If the
upstream map conflicts with local notes, stop and request human review.

