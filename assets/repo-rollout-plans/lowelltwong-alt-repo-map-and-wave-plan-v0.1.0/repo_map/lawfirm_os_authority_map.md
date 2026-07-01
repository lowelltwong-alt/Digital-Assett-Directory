# LawFirm OS Authority Map — DAD Rollout Posture

## Confirmed repo family shape from README/front-door inspection

```text
LawFirm-os-semantic-substrate      -> canonical semantic/governance control plane
LawFirm-os-skills-registry         -> skill supply chain
LawFirm-os-orchestrator            -> execution plane, consumes substrate read-only
LawFirm-os-exceptions-lake-runtime -> evidence plane / runtime evidence, no canon mutation
LawFirm-os-legal-knowledge-runtime -> legal knowledge/runtime context-bundle layer
LawFirm-os-intake                  -> vertical workflow composition, owns no platform canon
LawFirm-os-talent-intelligence     -> runtime/feature repo, not substrate
```

## DAD's role

DAD should be the reusable asset/control hub for preflight profiles, managed pointers, mail transport, asset lifecycle, lessons, and repo rollout state.

DAD must not claim to override the Semantic Substrate's canonical governance role inside LawFirm OS.

## Placement recommendation

```text
DAD                                      full master assets
LawFirm-os-semantic-substrate            governance pointer only
LawFirm-os-skills-registry               skill wrapper / DAD asset pointer
Execution/evidence/knowledge runtimes    managed pointer + mailbox, no full asset copy
Vertical repos                           managed pointer + mailbox after inventory
```
