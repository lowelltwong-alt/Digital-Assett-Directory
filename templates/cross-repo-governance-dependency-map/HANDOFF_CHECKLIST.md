# Governance Dependency Map Handoff Checklist

Use this checklist when handing off a repo-family governance-map adoption.

- Upstream governance repo and owner/review body named.
- Child repos listed with local mirror status.
- Actual authority language reviewed and adapted.
- Domain-specific seed language removed.
- `GOVERNANCE_DEPENDENCY_MAP.yaml` added or updated.
- Child `governance_dependency_map_mirror.yaml` added where needed.
- AI front door and AI TOC route agents to the map or mirror.
- Repo contract states non-override and fail-closed behavior.
- PR-description requirements include governance map/mirror review.
- Validator and test run locally.
- CI or aggregate validation includes the validator, when appropriate.
- Remaining human decisions and risks are listed.

