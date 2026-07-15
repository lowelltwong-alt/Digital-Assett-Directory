# Technical Product Capability Operating System — Build Evidence v1

Date: 2026-07-14
Branch: `codex/agent-family-portfolio-roadmap-20260714`
Preflight trace: `dad:trace:9a463c1c-d6a5-53d0-8172-784491a66aab`

## Delivered outcome

DAD now has one model-neutral technical-product capability operating layer for a
single human operator. It routes the smallest applicable capabilities, records
revision-aware routes and workflow runs, projects usage/freshness/gaps, publishes
a typed operational dependency graph, and folds no more than three candidate
decisions into the existing family cockpit. Luna, Terra, and Sol remain runtime
capability tiers rather than vendor model identifiers.

The first-ten portfolio is registered in priority order: technical-product
architecture; quality/verification/release; security/privacy/supply chain;
platform/cloud/SRE; data/schema/knowledge graph; integration/MCP/automation;
product/UX/accessibility; observability/incident resilience; developer
platform/DevEx; and product intelligence/experimentation. ML and full-stack
families are shared foundations. Product manager, product catalyst, capability-gap
sentinel, improvement steward, and independent checker roles are included in the
company-OS skill.

## AI decision-rights boundary

| Right | Eligible consequence tiers | Required control |
|---|---|---|
| Observe | C0 | Read-only, privacy-safe metadata |
| Retrieve / recommend | C0-C3 | Authority and eligibility checks; candidate only |
| Draft | C1-C2 | Named actor and required gates; no external effect |
| Validate | C1-C3 | Named checker, raw evidence, producer/checker separation |
| Execute | C2-C3 | Digest, human approval, checker evaluation, domain gate, rollback, unexpired lease, final confirmation, and trusted verifier |
| Prohibited / C4 | None | Always denied |

The current implementation deliberately has no trusted execution verifier, so
even a policy-complete C3 declaration remains non-executable. Routines are dormant
until explicitly activated, perform zero model calls on unchanged cycles, cannot
notify or mutate externally, and emit human-gated candidates only. The Cursor
adapter is registered but unauthorized; no external dispatch was performed.

## Integrity and one-human controls

- Exact/strong lexical routing is bounded to three primary capabilities; negative
  intent, privacy, permission, lifecycle, environment, and tool gates fail closed.
- Workflow activation requires positive exact workflow intent; capability overlap
  alone cannot launch a workflow.
- Usage counts only materially retrieved query matches, not catalog enumeration.
  Synthetic fixtures and unsupported validation claims cannot improve metrics.
- Producers cannot validate their own work. Run events require an effective route,
  selected workflow revision, valid lifecycle, and linked capabilities.
- Route and run corrections require an existing, effective, older, same-scope
  target; self, orphan, stale-target, and type/evidence-inconsistent corrections
  are rejected.
- Telemetry rejects secret-looking strings. Stored task references are opaque and
  graph edges preserve provenance without copying payloads.
- Daemon nested failures are folded into health instead of producing false-green
  cycles. Stable small control files use content fingerprints.

## Validation evidence

- `python -m pytest -q` — passed 1,571 tests in 724.3 seconds.
- Focused Capability OS regression — passed 23 tests after final corrections.
- Combined portfolio, role, navigation, library, MCP, and structured-pack
  regression — passed 187 tests before the two final focused hardening tests;
  independent frozen replay passed 148 selected tests after the fixes.
- `python -m digital_asset_directory.cli validate --hub .` — valid; 276 checks,
  zero warnings, zero errors.
- `python scripts/validate_agent_skill_library.py` — 33 skills valid.
- Official `quick_validate.py` — all five new skills valid.
- `python -m digital_asset_directory.cli roadmap check --no-update` — passed.
- `python -m py_compile ...` and JSON parsing of registries/schemas — passed.
- Independent frozen acceptance review — PASS, 97/100; zero P1 or P2 blockers.

Earlier full-suite attempts exposed twelve daemon/role/transport regressions and a
too-short wrapper. Those defects were fixed, their affected tests passed, and the
final full serial suite above passed. The wrapper timeout was not treated as a
test pass or a product failure.

## Confirmed, inferred, and unknown

Confirmed: model-neutral role contracts, ten-capability portfolio, deterministic
routing, AI authority evaluation, append-only telemetry, correction integrity,
workflow revision metrics, gap discovery, routines, operational graph, cockpit
folding, daemon hardening, and registry/navigation integration are implemented and
validated locally.

Inferred: the compact decision digest, quiet delta routines, and deterministic
preflight should materially reduce attention and token cost for a single operator.
This must be measured during real use; local tests do not prove operator workload
or downstream product outcomes.

Unknown / intentionally untested: no trusted C3 executor, scheduler activation,
external Cursor dispatch, external system mutation, or downstream DAD/Mock Trial
production pilot was authorized. These remain explicit future human-gated pilots,
not hidden completion claims.

## Reusable lessons and remaining risks

Reusable lessons: distinguish catalog enumeration from material retrieval in
usage metrics; validate append-only correction references before projection; fold
nested subsystem errors before declaring daemon health; supervise silent long test
runs with measured bounds and focused fast lanes while retaining one final serial
parity pass.

Remaining risks: the adversarial corpus is finite; real-world routing thresholds
need outcome feedback; routine activation and trusted execution need separate
security/governance reviews; and downstream integrations retain their own source
authority and approval requirements.
