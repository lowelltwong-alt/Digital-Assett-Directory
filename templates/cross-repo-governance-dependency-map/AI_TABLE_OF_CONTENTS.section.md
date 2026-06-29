| Path | What it is | Tags | Use when |
|---|---|---|---|
| `governance/GOVERNANCE_DEPENDENCY_MAP.yaml` | Machine-readable upstream governance dependency map and companion-surface update gate. | `governance`, `cross_repo`, `validation` | You change governance-facing files, repo authority, PR requirements, validators, front doors, or child mirror controls. |
| `.ai/control/governance_dependency_map_mirror.yaml` | Child-repo local mirror of the upstream governance dependency-map gate. | `governance`, `cross_repo`, `authority` | You work in a child repo and need the local non-override and drift-check rules. |
| `scripts/validate_governance_dependency_map.py` | Upstream validator for map shape, coverage, and changed-path review. | `validation`, `governance` | You need fail-closed proof that the map and governance-facing changes agree. |
| `scripts/validate_governance_dependency_map_mirror.py` | Child-repo validator for local mirror shape and discovery-surface references. | `validation`, `cross_repo` | You need proof a child repo still mirrors upstream governance without overriding it. |

