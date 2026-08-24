# Evidence Index

This file is an append-only pointer index. It must never become a second account
of what happened. Raw evidence, machine receipts, test output, external-state
snapshots, and independent reviews live under `checks/evidence/` or at the exact
immutable URL/path named here.

## Evidence rules

- Add a row; do not edit an old row except to append a clearly labeled correction.
- Record the source revision, command or API query, timestamp, producer, checker,
  privacy class, and digest when available.
- Do not store secrets, raw conversations, private source rows, or client data.
- A generated report is candidate evidence until its source and method are
  independently checked.
- A test PASS is attempt evidence, not a capability or business-value score.
- Missing evidence is `missing` or `coverage_unavailable`, never zero or green.

## Seed audit evidence

| Evidence ID | Phase/job | Status | Pointer | Notes |
|---|---|---|---|---|
| E-AUDIT-001 | Charter | observed | `dad:trace:4a713ca1-a47d-53c2-901f-18c95a5a44f4` | Prior whole-repo high-value audit trace. |
| E-AUDIT-002 | Charter | observed | `dad:handoff:08ef66d2-6977-5362-996e-4341d562625a` | Prior audit handoff. |
| E-AUDIT-003 | Charter | candidate lesson | `dad:lesson:fb112433-95c1-51af-9776-8217a0a7c23f` | Audit lesson; local artifacts remain authoritative. |

## Campaign evidence register

Append rows during execution.

| Evidence ID | Phase/job | Result | Produced at | Producer | Independent checker | Path or URL | Digest | Privacy | Correction/supersession |
|---|---|---|---|---|---|---|---|---|---|
| E-PRELAUNCH-005 | Prelaunch/revision 5 | bounded hook repair accepted; launch blocked | 2026-08-22T03:29:22Z | Codex bounded writer | non-author read-only checker | `checks/evidence/launch/qualifications/hook-latency-repair.json`; `checks/evidence/launch/independent-launch-review-revision-5.json` | `sha256:7d39df63638ddebfece1aacff4870e3a8e13b502ee3a9ef611e7960d5c270df7`; `sha256:b5d6633bd473a321fb7d87ac319737691932bfe2cd15e94a2b52d853a4038098` | synthetic internal metadata | Supersedes only revision-4 hook-latency blocker; does not supersede H-010, tracking, host-trust, or repository-policy blockers. |
| E-PRELAUNCH-006 | Prelaunch/revision 6 | bounded execution-control repair accepted; launch/H-010/J-100 blocked | 2026-08-23T05:27:04Z | Codex bounded writer | non-author read-only checker | `checks/evidence/launch/qualifications/prelaunch-revision-6.json`; `checks/evidence/launch/independent-launch-review-revision-6.json` | `sha256:a648fb704e9578cc8b40b8948658788576f5df5810bb073e8df936352878254b`; `sha256:f1d058c3762084045732c5efc46d121f5ed4391b843846fc5c67baaf539841d1` | synthetic internal metadata | Adds a real signed public-fold control proof and resolves volatile timestamp binding; does not authorize launch, H-010, J-100, tracking, commit, or business-value claims. |
| pending | P1/J-100 | missing | — | — | — | `checks/evidence/phase-1/` | — | internal metadata | — |
| pending | P1/J-110 | missing | — | — | — | `checks/evidence/phase-1/` | — | internal metadata | — |
| pending | P2/J-200 | missing | — | — | — | `checks/evidence/phase-2/` | — | internal metadata | — |
| pending | P2/J-210 | missing | — | — | — | `checks/evidence/phase-2/` | — | internal metadata | — |
| pending | P2/J-215 | missing | — | — | — | `checks/evidence/phase-2/` | — | internal metadata | — |
| pending | P3/J-300 | missing | — | — | — | `checks/evidence/phase-3/` | — | internal metadata | — |
| pending | P3/J-310 | missing | — | — | — | `checks/evidence/phase-3/` | — | internal metadata | — |
| pending | P3/J-320 | missing | — | — | — | `checks/evidence/phase-3/` | — | internal metadata | — |
| pending | P4/J-400 | missing | — | — | — | `checks/evidence/phase-4/` | — | private metadata | — |
| pending | P4/J-410 | missing | — | — | — | `checks/evidence/phase-4/` | — | internal metadata | — |
| pending | P5/J-500 | missing | — | — | — | `checks/evidence/pilot/` | — | scope-dependent | — |
| pending | P5/J-510 | missing | — | — | — | `checks/evidence/pilot/` | — | scope-dependent | — |
| pending | P5/J-520 | missing | — | — | — | `checks/evidence/pilot/` | — | scope-dependent | — |
| pending | P5/J-530 | missing | — | — | — | `checks/evidence/pilot/` | — | scope-dependent | — |
| pending | P6/J-600 | missing | — | — | — | `checks/evidence/decision/` | — | internal metadata | — |
