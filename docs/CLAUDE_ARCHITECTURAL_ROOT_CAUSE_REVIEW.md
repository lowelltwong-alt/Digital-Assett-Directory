# Claude Architectural Root-Cause Review Packets

Status: reviewed DAD guidance for integration and implementation issue patterns.

## Purpose

Some failures are not just local bugs. Repeated integration failures,
implementation stalls, and surprising side effects often point to an
architectural root cause: unclear ownership, wrong boundary, missing contract,
bad sequencing, stale generated evidence, or a control-plane mismatch.

DAD should preserve those patterns in a Claude-readable packet so Claude can
review root cause without needing raw logs, private data, copied source, or chat
rescues from Lowell.

This is an advisory capture lane. It does not replace exception events, fix
outcomes, harnesses, postflight, or local repo authority.

## Capture When

Create or suggest a root-cause packet when an issue has one or more signals:

- two or more integration failures around the same boundary;
- an implementation fix changes location because the first target was wrong;
- a test passes locally but fails when wired into another layer;
- source authority, generated evidence, registry, schema, or template ownership
  is unclear;
- a repo needs repeated manual rescue to emit the right DAD mail or exception;
- a workaround works but leaves a pattern likely to recur;
- a validator or hard gate feels too bulky and may need a harness instead;
- Claude, Fable, Codex, Cursor, or a human review points at architecture rather
  than a single-line defect.

Do not create one for a trivial typo, isolated missing import, or obvious
one-command local fix unless it repeats or reveals a boundary problem.

## Architecture Signals

Tag the packet with the smallest useful set of signal labels:

| Signal | Meaning |
| --- | --- |
| `boundary_mismatch` | Code, data, mail, or authority crossed the wrong boundary. |
| `ownership_ambiguity` | No clear owner for a contract, generated file, source truth, or fix outcome. |
| `sequencing_error` | Work happened in the wrong order or before a required gate. |
| `contract_gap` | A schema, interface, packet, or template lacked required fields. |
| `generated_evidence_drift` | A report, manifest, hash, or generated snapshot looked current but was stale. |
| `integration_surface_mismatch` | Two components were individually plausible but failed together. |
| `harness_gap` | A reusable harness or subharness should have caught the pattern. |
| `over_enforcement` | A deterministic check created bulk, false positives, or blocked learning. |
| `under_enforcement` | A missing hard check allowed false green, sensitive movement, or boundary drift. |
| `source_authority_confusion` | DAD or another control plane risked overriding local source authority. |

## Minimal Packet

Use safe metadata only.

```json
{
  "packet_type": "architectural_root_cause_review",
  "review_target": "claude",
  "source_repo": "repo-id-or-alias",
  "source_visibility": "private|internal|restricted|public|unknown",
  "stage": "preflight|midflight|postflight|review|ci|runtime",
  "safe_summary": "Short description of the recurring integration or implementation issue.",
  "symptom_refs": ["test-ref-or-safe-path-hash"],
  "boundary_refs": ["schema:mail-message", "component:mail_center"],
  "architecture_signals": ["boundary_mismatch", "contract_gap"],
  "suspected_root_causes": ["The source and generated report authority boundary is unclear."],
  "attempted_fixes": ["safe summary of attempted fix or approach change"],
  "validation_refs": ["python -m pytest tests/test_x.py -q"],
  "related_assets": ["docs/HARNESS_VS_DETERMINISTIC_ENFORCEMENT.md"],
  "harness_or_enforcement_question": "Should this become a harness, advisory warning, or hard check?",
  "claude_questions": [
    "What is the likely architectural root cause?",
    "Which boundary or contract should change?",
    "What test, harness, or migration would prevent recurrence?"
  ],
  "do_not_include": ["raw logs", "stack traces", "private rows", "source blobs", "secrets"]
}
```

## Claude Review Prompt

```text
You are reviewing a DAD architectural root-cause packet.

Treat the packet as candidate evidence. Do not assume the suspected cause is
true. Look for repeated integration or implementation patterns, not just the
last visible error.

Please return:
1. likely root cause;
2. alternative root causes that would explain the same symptoms;
3. which boundary, contract, sequencing, ownership, or architecture surface is
   implicated;
4. whether the next action should be a harness, advisory warning, deterministic
   enforcement, migration, or documentation fix;
5. what evidence would falsify your conclusion;
6. minimal tests or synthetic cases that would prevent recurrence;
7. risks if DAD overgeneralizes this lesson.

Do not request secrets, raw logs, private rows, full source files, hidden
reasoning, or copied transcripts.
```

## Where Packets Go

Repos should send these as candidate DAD mail or exception metadata:

- DAD need: `dad:need:integration-implementation-root-cause-patterns`
- DAD offering: `dad:offering:claude-architectural-root-cause-review`
- Exception lake event type: usually `review_finding`, `code_change_exception`,
  `fixture_or_synthetic_data_gap`, `generated_code_compile_failure`,
  `data_ingestion_failure`, or `identity_resolution_conflict`
- Harness decision model: `docs/HARNESS_VS_DETERMINISTIC_ENFORCEMENT.md`

If the issue is still active, the packet is a midflight review request. If the
issue is fixed, attach a fix outcome and validation refs so DAD can learn from
the repair.

## Non-Goals

- Do not use Claude review as human approval.
- Do not use the packet to bypass public/private release gates.
- Do not store raw diagnostic output or private content in DAD.
- Do not turn one packet into a universal rule without non-applicability notes.
- Do not add deterministic enforcement until the stable, objective slice is
  clear.

## Authority Boundary

Claude root-cause review is candidate analysis. It can suggest a harness,
migration, contract change, or hard gate, but local repo authority and DAD's
human gates decide adoption.
