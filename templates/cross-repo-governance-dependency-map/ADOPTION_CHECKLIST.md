# Cross-Repo Governance Dependency Map Adoption Checklist

Use this template seed when a repo family needs deterministic governance
mapping from day one.

## Adopt

- Identify the upstream/control-plane repo.
- Identify child repos and what they may mirror.
- Replace every `{{PLACEHOLDER}}` with repo-specific names, paths, trust zones,
  and approval references.
- Add or update the upstream map.
- Add child mirrors only where a child repo is explicitly approved for local
  governance controls.
- Add front-door, TOC, repo-contract, README, and PR-description sections.
- Add validator and test files.
- Add the validator to CI or the repo's aggregate validation command.

## Validate

```powershell
python scripts/validate_governance_dependency_map.py
python -m pytest tests/test_governance_dependency_map.py
```

For child mirrors:

```powershell
python scripts/validate_governance_dependency_map_mirror.py
python -m pytest tests/test_governance_dependency_map_mirror.py
```

## Do Not

- Do not let a child repo override upstream governance.
- Do not copy another domain's source rules.
- Do not replace validators with prose.
- Do not mark the adoption complete until the map, mirror, discovery surfaces,
  repo contract, PR description, validator, and test agree.

