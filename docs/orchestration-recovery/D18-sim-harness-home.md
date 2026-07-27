# D18 — Home of the shared simulation harness (`lawfirm-os-sim-harness`)

Status: **OPEN — recommendation recorded, awaiting owner confirmation**
Raised: 2026-07-09 by Fable (boss)
Owner: Lowell T. Wong

## Question

Where does the shared executable library live — the `harness/` package (run manifests, seed
control, simulation run records, label-free eval/calibration, red-team fixtures, score-language
guard, human-adoption gate, no-write discipline, provenance) and the `montecarlo/` kernel
(shared only by ALS and billing-guideline-simulator)?

## Options

| Option | Pros | Cons |
|---|---|---|
| **(a) New repo `lawfirm-os-sim-harness`** (recommended) | Clean plane separation; pinnable by SHA like every other dependency; registered in the Substrate repo registry with its own boundary doc; no role-mixing | One more repo to govern |
| (b) Package inside Skills Registry | No new repo | Mixes the supply-chain evaluation role with a runtime library; skills-registry "must not own" runtime execution surfaces; consumers would pin a repo whose primary churn is unrelated skill traffic |
| (c) Package inside Orchestrator | Execution-plane adjacency | Couples four engines (two of them external/adapter-only) to the orchestrator's release cadence; ALS must not depend on a LawFirm OS authority-plane repo |

## Recommendation

**(a)** — new repo, `authority_plane: none`, registered in
`LawFirm-os-semantic-substrate/registry/lawfirm-os-repo-registry.json` (which fails validation on
unregistered `LawFirm-os-*` repos), consumed by pinned SHA from ALS, billing-sim, intake B, and
orphan_radar. Contracts (simulation-run-manifest, simulation-run-record, simulation-eval-report,
score-language-policy) are promoted to Substrate; the library implements them.

## Blocking paths

- P3 extraction PRs (harness + montecarlo extraction). **Not blocked:** P3 characterization
  tests (T-0009..T-0012) — they land inside each engine repo and are prerequisite anyway.

## Safe placeholder

Characterization tests proceed; no shared code is created; no duplicated code is deleted.

## Risk if guessed

Wrong home = repo-registry validation failures, role-mixing in the supply chain plane, or an
external simulator (ALS) coupled to a LawFirm OS authority repo.

## Resolution

(unfilled)
