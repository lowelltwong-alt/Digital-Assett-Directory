# D18 — Home of the shared simulation harness (`lawfirm-os-sim-harness`)

Status: **RESOLVED 2026-07-27 — option (a) approved; repo creation deferred to extraction time**
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

## Resolution — 2026-07-27

Approved by: **Lowell T. Wong** (in-session decision, options and tradeoffs presented)

**Option (a) confirmed.** The shared `harness/` package and `montecarlo/` kernel get their own
repo, `lawfirm-os-sim-harness`, `authority_plane: none`, registered in
`LawFirm-os-semantic-substrate/registry/lawfirm-os-repo-registry.json`, consumed by pinned SHA.
The rejection reasons for (b) and (c) hold: Skills Registry must not own a runtime execution
library (role-mixing in the supply-chain plane), and Orchestrator is worse, because ALS is
external and must not depend on a LawFirm OS authority-plane repo.

### Deciding is not creating

The repo is **not created yet**. This record's own blocking analysis notes that P3 extraction PRs
are blocked on D18 while the characterization tests (T-0009…T-0012) are prerequisite and *not*
blocked. Creating an empty governed repo before the extracted code exists would contradict the
standing portfolio rule that a repository should not exist before the evidence it holds.

**Creation trigger:** P3 characterization tests complete and the first extraction PR is ready.
At that point: create the repo, register it in the substrate repo registry (which fails
validation on unregistered `LawFirm-os-*` names), add its boundary doc, and promote the four
contracts (simulation-run-manifest, simulation-run-record, simulation-eval-report,
score-language-policy) to Substrate with the library implementing them.

### Boundary against the Wave 3 evaluation harness

Recorded because the names would otherwise blur, and both were about to be built.

| | `lawfirm-os-sim-harness` (this decision) | Wave 3 comparative harness |
|---|---|---|
| Question it answers | "run this simulation reproducibly" | "which implementation strategy is better on the same held-out cases" |
| Scope | run manifests, seed control, simulation run records, MC kernel, label-free eval/calibration, red-team fixtures, score-language guard | condition runner (deterministic / retrieval-assisted / bounded-agent), contamination-controlled holdout split, graders, condition-comparison records |
| Consumers | ALS, billing-guideline-simulator, intake, orphan_radar | intake only, initially |
| Home | new repo, pinned by SHA | **inside `LawFirm-os-intake`**, where the workflow, fixtures, and adapters already are |

Wave 3 does **not** wait on this repo and does not pre-empt it. If genuine duplication emerges
once both exist, the shared part is extracted into the sim-harness repo later — the same
evidence-first sequence applied here.
