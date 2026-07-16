# ML Expert Mesh Delta Integration

Status: implemented candidate, read-only routing only
Date: 2026-07-16

## Decision

DAD's existing `skill:ml-workflow-agent-family` remains the single ML family.
The attached `ml-expert-mesh-starter.zip` was evaluated as candidate evidence,
not imported as code or canon. Its archive SHA-256 was
`2EF8A6BC5FDF78C63E3C47356E52EB80C040BE3E291A3D49C782C17F033E2FFB`.
The archive declares no selected license, contains a parallel router and
deployment stack, and duplicates many agent/configuration files. None of its
source, agent folders, knowledge files, provider adapters, approval logic,
Docker/Kubernetes files, caches, or package metadata were copied into DAD.

## Useful Delta Implemented DAD's Way

1. `workflow:ml-opportunity-review` is now the mandatory first hop within DAD's
   governed ML routing interface.
2. `asset-dir ml fit` emits a schema-validated, deterministic, provider-neutral,
   read-only assessment receipt.
3. `asset-dir ml specialist-route` validates the complete receipt payload,
   current policy revision, identity, and nested digest before returning a
   bounded technique-router candidate. The receipt grants no dispatch or
   execution authority. External routes that bypass DAD remain outside measured
   enforcement coverage.
4. A named tool, model, provider, library, or specialist cannot bypass fit.
5. The result is an ordered toolchain: simplest credible baseline first, then
   optional stages with entry and stop criteria plus rejected alternatives.
6. Distributed execution requires measured local insufficiency or an approved
   hard constraint. One deep-learning backend is the default.
7. Retrieval, RAG, long-context, vector, and graph problems hand off to DAD's
   existing Knowledge Engineering family rather than duplicating it in ML.
8. The ML decision schema now requires the supported action, reversibility,
   abstention behavior, asymmetric error/delay/review costs, prediction-time
   availability, and maintenance owner.
9. The portfolio graph's dangling `role:ml-workflow-sentinel` reference now
   points to the declared `role:ml-lifecycle-curator` responsibility.
10. UTF-8 portability digests normalize CRLF/LF checkout differences while
    binary artifacts remain byte-exact, preventing false staleness across
    worktrees and operating-system Git settings.

## Contract Revision

This is an explicit `0.2.0` revision of the ML family registry and completed ML
workflow-decision schema. Historical `0.1.0` decision artifacts remain
historical evidence; they are not silently reinterpreted. A producer migrating
to `0.2.0` must add the supported action, reversibility, abstention behavior,
decision-cost map, prediction-time availability, and maintenance owner. The
new compact fit-request schema is the opportunity workflow input; the full ML
workflow decision remains a later reviewed artifact.

## Deliberately Not Built

- A second ML package, service, CLI, hierarchy, provider adapter layer, or
  deployment stack.
- One agent per ML library or framework.
- Automatic training, data access, research activation, deployment, or
  instruction mutation.
- Arbitrary row-count thresholds, popularity routing, boolean approval as
  authority, or a universal model/tool score.
- A duplicate retrieval/RAG/knowledge-graph family.

## Authority and Remaining Work

The fit route is candidate-only and read-only. It does not establish that an ML
role is competent on a live runtime, authorize data access, or prove an actual
model works. Runtime qualification, cross-model A/B evidence, a bounded
synthetic end-to-end ML pilot, and activation of the already-defined fortnightly
research cycle remain separate human-gated work. They should be added only with
revision-bound evidence and without turning candidate routing into execution.
