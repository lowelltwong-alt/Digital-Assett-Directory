# Self-Learning and Improvement Plan — Independent Review

Date: 2026-07-15
Reviewer role: independent checker, read-only
Final disposition: **pass for manual Fable review; not authority to begin Phase 1**

## Reviewed artifacts

- `docs/research/AI_SELF_LEARNING_AND_IMPROVEMENT_RESEARCH_2026-07-14.md`
- `docs/SELF_LEARNING_IMPROVEMENT_SYSTEM_PLAN.md`
- `docs/FABLE_SELF_LEARNING_IMPROVEMENT_SYSTEM_PROMPT.md`
- `roadmap/evidence/self-learning-improvement-task-mesh-r1.json`
- AI navigation changes

## Initial blockers and resolution

| Blocker | Resolution | Recheck |
|---|---|---|
| T4/T5 was conflated with categorically prohibited C4 authority | Update surface is now separate from consequence. Bounded T4/T5 experiments require exact C2/C3 classification and approval; autonomous/production self-modification remains C4 prohibited. | passed |
| Weekly arXiv RSS could miss intervening daily feed contents | Weekly discovery now uses submitted/updated-date API windows with overlap; RSS is announcement-only unless an approved deterministic daily snapshot exists. An eight-day exactly-once fixture is required. | passed |
| Luna and Terra stage budgets exceeded the stated normal total | Both stages now reserve from one 116,000-token normal envelope; 300,000 remains a separately recorded material-delta ceiling. | passed |
| Agent roles appeared to own Fable and routine-activation decisions | The mesh now has a non-agent `human-owner` authority role. Lowell exclusively owns Fable, activation, adoption, budget, and phase decisions. Fable review blocks Phase 1. | passed |
| Phase 2 attempted too many workflows for one operator | The catalog remains 45 workflows, but Phase 2 implements only an eight-workflow candidate-only MVP; all others remain dormant pending usage evidence. | passed |

Material follow-ups also incorporated: multi-label T0-T5 surfaces, source-specific
collection contracts, Crossref enrichment-only scope, sequential-testing
controls, rollback-corruption rehearsal, memory/data revocation propagation,
license/supply-chain checks, independent reference labels instead of treating
governance decisions as correctness, one-human time/backlog metrics, and a
12,000-output-token Fable ceiling.

## Validation evidence

Run from the isolated worktree with `PYTHONPATH=src` and explicit `--hub .` so
the DAD locator cannot redirect validation to another checkout:

```text
python -m pytest tests/test_ai_navigation.py tests/test_ml_agent_family.py tests/test_agent_family_portfolio.py tests/test_technical_product_company_os.py -q
60 passed

python -m digital_asset_directory.cli validate --hub .
valid: true; checked_count: 277; warning_count: 0; errors: []

python .../validate_agent_mesh_manifest.py roadmap/evidence/self-learning-improvement-task-mesh-r1.json
valid at independent recheck; the final evidence-ledger update produces
sha256:ac46cd08be44f09aa8a5b7e721dda89b2d11fbdeb3c19a582adb487b50ac0d6c

git diff --check
passed; line-ending notices only
```

An earlier validator invocation without `--hub .` resolved through the user-level
locator to a different checkout and reported a missing current registry. That was
an invocation-scope error, not evidence about this worktree. The explicit-hub
canonical validation above is green.

## Residual gates

- Lowell must decide whether to copy the sanitized packet to Fable and approve
  its one-time token budget.
- Fable's strongest disagreement must be reconciled and independently rechecked.
- Lowell must then approve or reject Phase 1. No approval is implied here.
- The P7D routine, connectors, notifications, optimizers, instruction edits,
  training, deployment, and external mutations remain dormant.
