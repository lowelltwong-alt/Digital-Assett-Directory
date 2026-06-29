## Governance Dependency Map Review

- Did this PR change governance-facing paths? `yes/no`
- If yes, were these companion surfaces reviewed?
  - `governance/GOVERNANCE_DEPENDENCY_MAP.yaml`
  - child repo mirror files
  - `AI_FRONT_DOOR.md`
  - `AI_TABLE_OF_CONTENTS.md`
  - repo contract / `AGENTS.md`
  - `README.md`
  - validator scripts
  - tests
- If no map or mirror update was needed, explain why.
- Confirm this PR does not let a child repo override upstream governance.

## Validation

- `python scripts/validate_governance_dependency_map.py`
- `python -m pytest tests/test_governance_dependency_map.py`
- Child mirror, if present:
  - `python scripts/validate_governance_dependency_map_mirror.py`
  - `python -m pytest tests/test_governance_dependency_map_mirror.py`

