# CI Module Boundary Governance Decision

Status: candidate capability revision 0.1.0; risk tier high.

## Decision

Ordinary PR checks follow declared module ownership and dependency edges. A
module suite runs for its code, contracts, authoritative inputs, and declared
upstream changes that reach it as a direct dependent. Integration and release
suites require explicit scope and edges. Scheduled full-system regression is a
separate lane.

The provider-neutral manifest and deterministic evaluator are authoritative.
CI-provider workflows are adapters and cannot broaden scope.

## Dedupe and reuse

Deterministic DAD search found no exact rule or capability. This is a new
distinct capability composed with:

- 'dad:harness:python-test-performance-orchestration' for local test selection;
- 'template:cross-repo-governance-dependency-map' for fail-closed dependency maps;
- 'ci-release-artifact-scope-v0.1' for metadata-only adoption inventory.

No source case name, client material, raw conversation, or private payload is
stored. The incident reference is only
'sha256:6631e5cb9401a75014b942a0d20cd015654ec2b54d6b9af5871b9e377733ef0a'.

## Options

1. Chosen: provider-neutral manifest, deterministic evaluator, thin adapters.
2. Rejected: provider-native path filters only; they cannot prove transitive
   dependents, scope drift, required-check behavior, or portability.
3. Rejected: retain repository-wide ordinary PR suites; unrelated modules can
   block one another without a declared integration or release dependency.

## Blast radius and controls

Affected surfaces include CI contracts, schemas, validators, workflows,
templates, registries, agent routing, new-project scaffolds, and downstream
recommendations. Source repositories retain adoption authority.

Kill criteria:

- a real declared dependent is silently skipped;
- an unexplained repository-wide module workflow passes;
- an expired or unreviewed exception is accepted;
- a path-filtered required check can deadlock;
- a provider adapter broadens normative selection.

Rollback removes activation pointers and provider adapters while retaining the
manifest and evidence as candidate records. Negative fixtures compare scoped
selection with repository-wide behavior. Fresh-eyes review is required before
promotion.

## Remaining epistemic boundary

No generic changed-path tool can prove that all semantic dependency edges were
declared. When observed dependency evidence is unavailable, the validator
reports 'coverage_unavailable'. Local owners must review the graph and supply
observed-edge evidence before claiming completeness.
