---
name: portable-capability-governance
description: Apply DAD's deterministic portability contract and behavioral harnesses whenever a reusable skill, agent, subagent pack, workflow, harness, prompt, library, knowledge interface, template, or family is created, materially revised, exported, activated, promoted, replaced, or retired, including runtime/model/provider/tool/privacy/schema/dependency changes.
---

# DAD Portable Capability Governance

1. Apply the governing rule in
   `references/PORTABLE_CAPABILITY_CONTRACT.md` and search related DAD identities
   before creating a new one.
2. Run `asset-dir portability classify` and `asset-dir portability validate`.
   Treat registry, graph, score, and model results as candidate evidence.
3. Separate the provider-neutral core from separately revisioned adapters,
   probes, receipts, experiments, qualifications, exceptions, policies, and
   activation decisions.
4. Use deterministic validators for objective invariants and the registered
   harness plus a separate checker for semantic or behavioral compatibility.
5. Bind preflight, affected-slice midflight, and honest postflight to the exact
   portability assessment. Missing evidence blocks activation or protected
   release, not failure reporting.
6. Require verified receipts and the reviewed runtime-qualification methodology
   before claiming cross-model diversity or proposing a replacement. No result
   self-promotes.
7. Preserve local source authority, private corpus custody, at-most-three cockpit
   decisions, zero-model unchanged scans, immutable history, and safe rollback.

The DAD registry and CLI are lifecycle and evidence authorities only. They do
not authorize provider access, secrets, schedules, external effects, downstream
adoption, exception approval, model promotion, or control-plane self-activation.
